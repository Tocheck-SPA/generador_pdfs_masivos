"""Mapeo de respuesta cruda a cumplimiento, según la lógica oficial de ToCheck.

Referencia: consulta de origen usada por ai-supervisor.
    tipo_resp ∈ (1,2): respuesta=1 -> No Cumple (0), otro -> Cumple (1)
    tipo_resp = 4:     1 -> No Cumple (0), 2 -> Cumple Parcial (0.5), otro -> Cumple (1)
    resto:             1 -> No Cumple (0), 2/3/4 -> Cumple Parcial (0.5), otro -> Cumple (1)

Para fixtures (sin tipo_resp), cae a una heurística textual (Sí/Cumple/No...).
"""
from __future__ import annotations

CUMPLE = "Cumple"
PARCIAL = "Cumple Parcial"
NO_CUMPLE = "No Cumple"


def _as_int(value) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def evaluate(answer_raw, answer_type: int | None) -> tuple[str | None, float | None]:
    """Devuelve (etiqueta, valor 0..1) o (etiqueta_libre, None) si no es una pregunta de cumplimiento."""
    r = _as_int(answer_raw)
    if r is not None and answer_type is not None:
        if answer_type in (1, 2):
            return (NO_CUMPLE, 0.0) if r == 1 else (CUMPLE, 1.0)
        if answer_type == 4:
            if r == 1:
                return (NO_CUMPLE, 0.0)
            if r == 2:
                return (PARCIAL, 0.5)
            return (CUMPLE, 1.0)
        if r == 1:
            return (NO_CUMPLE, 0.0)
        if r in (2, 3, 4):
            return (PARCIAL, 0.5)
        return (CUMPLE, 1.0)

    # Heurística textual (fixtures / datos sin tipo_resp numérico)
    s = (str(answer_raw).strip().lower() if answer_raw is not None else "")
    if s in ("sí", "si", "cumple", "ok", "aprobado", "true", "si cumple"):
        return (CUMPLE, 1.0)
    if s in ("parcial", "cumple parcial", "medio", "observado"):
        return (PARCIAL, 0.5)
    if s in ("no", "no cumple", "false", "rechazado"):
        return (NO_CUMPLE, 0.0)
    # No es una pregunta de cumplimiento (texto libre, lista, etc.)
    return (str(answer_raw) if answer_raw is not None else None, None)
