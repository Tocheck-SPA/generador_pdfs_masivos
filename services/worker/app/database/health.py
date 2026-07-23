"""Estado de dependencias del worker (sin exponer secretos)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..config import Settings


def health_report(settings: Settings) -> str:
    database = "not_configured"
    source = "fixture" if settings.source_adapter == "fixture" else "not_configured"

    if settings.database_url:
        try:
            import psycopg

            with psycopg.connect(settings.database_url, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            database = "ok"
        except Exception:  # noqa: BLE001
            database = "error"

    if settings.source_adapter == "postgres" and settings.source_database_url:
        try:
            import psycopg

            with psycopg.connect(settings.source_database_url, connect_timeout=5,
                                 sslmode=settings.source_database_sslmode or "require") as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            source = "ok"
        except Exception:  # noqa: BLE001
            source = "error"

    overall = "ok" if database in ("ok", "not_configured") and source in ("ok", "fixture", "not_configured") else "degraded"
    return json.dumps({
        "status": overall,
        "database": database,
        "sourceDatabase": source,
        "worker_id": settings.worker_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False)
