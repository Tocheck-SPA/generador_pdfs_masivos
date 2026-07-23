"""Hash determinista del contenido visible de un informe para la caché de PDF.

Clave lógica = response_id + source_payload_hash + template_version + generator_version.
Se excluyen los datos binarios de imágenes (se representan por su ruta de origen)
y cualquier URL prefirmada temporal.
"""
from __future__ import annotations

import hashlib
import json

from .model import ReportData


def _canonical(data: ReportData) -> dict:
    payload = data.model_dump(mode="json", exclude={"warnings"})
    # Representar imágenes solo por su ruta de origen (no por el binario/data URI).
    for section in payload.get("sections", []):
        for question in section.get("questions", []):
            question["images"] = sorted(img.get("source_path", "") for img in question.get("images", []))
    return payload


def source_payload_hash(data: ReportData) -> str:
    canonical = _canonical(data)
    encoded = json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def cache_key(response_id: int, payload_hash: str, template_version: str, generator_version: str) -> str:
    raw = f"{response_id}:{payload_hash}:{template_version}:{generator_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
