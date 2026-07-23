"""Generación de nombres de archivo seguros.

Formato: YYYY-MM-DD_empresa_punto_formulario_response-id.pdf
minúsculas, sin tildes, espacios -> guion bajo, sin caracteres inválidos.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

_MAX_SLUG = 40


def slugify(value: str | None, fallback: str = "sd") -> str:
    if not value:
        return fallback
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_only = re.sub(r"[^a-z0-9]+", "_", ascii_only).strip("_")
    ascii_only = re.sub(r"_+", "_", ascii_only)
    return (ascii_only or fallback)[:_MAX_SLUG]


def pdf_filename(
    completed_at: datetime,
    company_name: str | None,
    point_or_entity: str | None,
    form_name: str | None,
    response_id: int,
) -> str:
    date_part = completed_at.strftime("%Y-%m-%d")
    parts = [
        date_part,
        slugify(company_name, "empresa"),
        slugify(point_or_entity, "punto"),
        slugify(form_name, "formulario"),
        str(response_id),
    ]
    return "_".join(parts) + ".pdf"


def zip_filename(company_name: str | None, date_from: datetime, date_to_inclusive: datetime) -> str:
    return (
        f"informes_{slugify(company_name, 'empresa')}"
        f"_{date_from.strftime('%Y-%m-%d')}_{date_to_inclusive.strftime('%Y-%m-%d')}.zip"
    )
