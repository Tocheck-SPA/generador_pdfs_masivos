"""Interfaz de almacenamiento de artefactos (R2 en prod, local en dev)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StoredObject:
    storage_key: str
    size_bytes: int
    content_type: str
    checksum: str
    storage_provider: str = "local"
    storage_bucket: str | None = None


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, content: bytes, content_type: str) -> StoredObject: ...

    @abstractmethod
    def presigned_url(self, key: str, expires_seconds: int) -> str:
        """URL temporal de descarga. NUNCA debe registrarse en logs."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...
