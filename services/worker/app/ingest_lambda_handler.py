"""AWS Lambda entrypoint for scheduled MySQL → Postgres snapshot ingest."""
from __future__ import annotations

from datetime import datetime

from .config import get_settings
from .source.ingest import get_last_synced_upper_bound, ingest_snapshot, resolve_ingest_window


def handler(event: dict | None, context) -> dict:
    event = event if isinstance(event, dict) else {}
    if event and event.get("schemaVersion") not in (None, 1):
        raise ValueError("Evento ingest inválido: schemaVersion debe ser 1")

    settings = get_settings()
    company_ids = _resolve_company_ids(event, settings)
    lookback_days = int(event.get("lookbackDays") or 7)
    if lookback_days < 1:
        raise ValueError("lookbackDays debe ser >= 1")

    # Backfill explícito: si viene dateFrom, NO se continúa desde el último sync.
    explicit_from = _parse_optional_dt(event.get("dateFrom"))
    explicit_to = _parse_optional_dt(event.get("dateToExclusive"))
    force_lookback = bool(event.get("forceLookback"))

    results = []
    for company_id in company_ids:
        last_upper = None
        if explicit_from is None and not force_lookback:
            last_upper = get_last_synced_upper_bound(settings, company_id)
        start, end = resolve_ingest_window(
            date_from=explicit_from,
            date_to_exclusive=explicit_to,
            last_synced_upper_bound=last_upper,
            lookback_days=lookback_days,
            now=datetime.now(),
        )
        result = ingest_snapshot(
            settings,
            company_id=company_id,
            date_from=start,
            date_to_exclusive=end,
        )
        results.append(
            {
                "companyId": company_id,
                "dateFrom": start.isoformat(),
                "dateToExclusive": end.isoformat(),
                **result,
            }
        )

    request_id = getattr(context, "aws_request_id", None)
    return {
        "schemaVersion": 1,
        "requestId": request_id,
        "companies": results,
    }


def _parse_optional_dt(raw: object) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _resolve_company_ids(event: dict, settings) -> list[int]:
    raw = event.get("companyIds") or event.get("companyId")
    if raw is None:
        if settings.source_company_id is None:
            raise ValueError(
                "Falta companyId/companyIds en el evento o SOURCE_COMPANY_ID en el entorno"
            )
        return [int(settings.source_company_id)]
    if isinstance(raw, list):
        ids = [int(x) for x in raw]
    else:
        ids = [int(x.strip()) for x in str(raw).split(",") if str(x).strip()]
    if not ids:
        raise ValueError("companyId/companyIds vacío")
    return ids
