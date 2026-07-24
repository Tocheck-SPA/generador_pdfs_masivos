"""Resolutor de assets (imágenes) aislado del generador de PDF.

La ruta almacenada en la fuente puede ser: URL completa, ruta relativa, key de
AWS/S3 o solo un nombre de archivo. El generador NO debe conocer estos detalles.

MVP: se resuelven URLs http(s) por descarga directa. La resolución de keys S3 /
rutas relativas requiere la base y credenciales de la fuente de imágenes, que aún
NO están confirmadas (ver docs/pending-fields.md). Ese caso queda como punto de
extensión explícito y devuelve `found=False` sin bloquear el job.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from .models import SourceAsset

_MAX_BYTES = 15 * 1024 * 1024  # límite de tamaño por imagen
_TIMEOUT = 20.0


def resolve_remote_asset(
    path: str, *, asset_base_url: str | None = None, local_dir: str | None = None
) -> SourceAsset:
    # 1) Fallback local por nombre de archivo (offline / pruebas / comparación).
    if local_dir:
        candidate = Path(local_dir) / Path(path).name
        if candidate.exists():
            ct, _ = mimetypes.guess_type(str(candidate))
            return SourceAsset(path=path, found=True, content=candidate.read_bytes(),
                               content_type=ct or "application/octet-stream")

    url: str | None = None
    if path.startswith("http://") or path.startswith("https://"):
        url = path
    elif asset_base_url:
        url = asset_base_url.rstrip("/") + "/" + path.lstrip("/")

    if url is None:
        # Punto de extensión: resolución de key S3 / ruta relativa pendiente de confirmar.
        return SourceAsset(path=path, found=False)

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content = resp.content
            if len(content) > _MAX_BYTES:
                return SourceAsset(path=path, found=False)
            content_type = resp.headers.get("content-type") or mimetypes.guess_type(url)[0]
            return SourceAsset(path=path, found=True, content=content,
                               content_type=content_type or "application/octet-stream")
    except httpx.HTTPError:
        return SourceAsset(path=path, found=False)
