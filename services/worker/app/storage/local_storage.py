"""Almacenamiento local en disco (desarrollo y pruebas)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .base import Storage, StoredObject


class LocalStorage(Storage):
    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._base / key

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StoredObject(
            storage_key=key,
            size_bytes=len(content),
            content_type=content_type,
            checksum=hashlib.sha256(content).hexdigest(),
        )

    def presigned_url(self, key: str, expires_seconds: int) -> str:
        # En local no hay firma; se devuelve una URL file:// para referencia.
        return self._path(key).resolve().as_uri()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()
