"""AWS S3 artifact storage using boto3's standard credential chain."""
from __future__ import annotations

import hashlib

from .base import Storage, StoredObject


class S3Storage(Storage):
    def __init__(self, *, bucket: str, region: str, endpoint: str = "") -> None:
        import boto3

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint or None,
        )

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return StoredObject(
            storage_key=key,
            size_bytes=len(content),
            content_type=content_type,
            checksum=hashlib.sha256(content).hexdigest(),
            storage_provider="s3",
            storage_bucket=self._bucket,
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
