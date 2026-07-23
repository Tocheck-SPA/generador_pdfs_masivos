"""Resolución y procesamiento de imágenes para el PDF.

- Resuelve la ruta vía el SourceRepository (aísla cómo funciona el almacenamiento).
- Corrige orientación EXIF, reduce dimensión, convierte a JPEG, controla calidad.
- Nunca bloquea todo el job si una imagen falla: marca warning y usa placeholder.
"""
from __future__ import annotations

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

from ..source.repository import SourceRepository
from .model import ReportData, ReportImage


def _to_data_uri(raw: bytes, max_dimension: int, jpeg_quality: int) -> str:
    with Image.open(io.BytesIO(raw)) as img:
        img = ImageOps.exif_transpose(img)  # corrige orientación
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((max_dimension, max_dimension))  # mantiene proporción
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def resolve_report_images(
    data: ReportData,
    repository: SourceRepository,
    *,
    max_dimension: int = 1600,
    jpeg_quality: int = 80,
) -> None:
    """Rellena `data_uri` de cada imagen in-place. Procesa una imagen a la vez."""
    for section in data.sections:
        for question in section.questions:
            resolved: list[ReportImage] = []
            for image in question.images:
                try:
                    asset = repository.resolve_asset(image.source_path)
                    if not asset.found or asset.content is None:
                        image.failed = True
                        data.warnings.append(f"Imagen no encontrada: {image.source_path}")
                    else:
                        image.data_uri = _to_data_uri(asset.content, max_dimension, jpeg_quality)
                except (UnidentifiedImageError, OSError, ValueError):
                    image.failed = True
                    data.warnings.append(f"No se pudo procesar la imagen: {image.source_path}")
                resolved.append(image)
            question.images = resolved
