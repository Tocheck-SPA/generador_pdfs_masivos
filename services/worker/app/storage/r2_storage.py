"""Almacenamiento en Cloudflare R2 (compatible S3) vía boto3."""
from __future__ import annotations

import hashlib

from .base import Storage, StoredObject


class R2Storage(Storage):
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        endpoint: str,
        region: str = "auto",
    ) -> None:
        import boto3  # import perezoso: no requerido en modo local

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint or f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=content_type)
        return StoredObject(
            storage_key=key,
            size_bytes=len(content),
            content_type=content_type,
            checksum=hashlib.sha256(content).hexdigest(),
        )

    def presigned_url(self, key: str, expires_seconds: int) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False
