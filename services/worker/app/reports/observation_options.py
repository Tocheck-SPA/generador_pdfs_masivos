"""Adaptador tolerante para el campo `opciones` de las listas de observación.

Soporta texto plano, JSON (lista o dict) y valores separados por comas, sin
romper si el formato cambia. Aislado para poder ajustarlo con datos reales.
"""
from __future__ import annotations

import json


def parse_observation_options(raw: str | None) -> list[str]:
    if raw is None:
        return []
    value = raw.strip()
    if not value:
        return []
    # 1) intentar JSON
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
        if isinstance(parsed, dict):
            return [str(v).strip() for v in parsed.values() if str(v).strip()]
        return [str(parsed).strip()]
    except (json.JSONDecodeError, ValueError):
        pass
    # 2) separado por comas / punto y coma
    if "," in value or ";" in value:
        parts = [p.strip() for chunk in value.split(";") for p in chunk.split(",")]
        return [p for p in parts if p]
    # 3) texto plano
    return [value]
