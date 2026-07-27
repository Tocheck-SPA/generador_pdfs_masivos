"""Ingesta local de MySQL hacia el snapshot operativo de Neon."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..config import Settings
from .models import ReportFilters
from .mysql_repository import MySQLSourceRepository


def get_last_synced_upper_bound(settings: Settings, company_id: int) -> datetime | None:
    """Último `date_to_exclusive` de una corrida COMPLETADA para la empresa.

    Se usa como punto de continuación exacto (con hora, minuto y segundo) de
    la próxima ingesta incremental, para no perder ni repetir respuestas que
    lleguen entre dos corridas del mismo día.
    """
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT MAX(date_to_exclusive) AS upper
                   FROM source_sync_runs
                   WHERE company_id = %s AND status = 'completed'""",
                (company_id,),
            )
            row = cur.fetchone()
    return row["upper"] if row and row.get("upper") else None


def resolve_ingest_window(
    *,
    date_from: datetime | None,
    date_to_exclusive: datetime | None,
    last_synced_upper_bound: datetime | None,
    lookback_days: int,
    now: datetime,
) -> tuple[datetime, datetime]:
    """Calcula la ventana [inicio, fin) de una corrida de ingesta.

    Prioridad del inicio:
      1. `date_from` explícito (override manual, p. ej. backfill inicial).
      2. El punto exacto (fecha+hora) donde terminó la última corrida
         completada para esta empresa — ingesta incremental real.
      3. `lookback_days` desde `now`, a medianoche, solo si nunca hubo una
         corrida completada (primera vez).

    El fin, si no se especifica, es `now` (no el día siguiente completo):
    así cada corrida cubre exactamente hasta el instante en que se ejecuta,
    y la siguiente continúa justo desde ahí sin huecos ni reprocesos.
    """
    if date_from is not None:
        start = date_from
    elif last_synced_upper_bound is not None:
        start = last_synced_upper_bound
    else:
        start = (now - timedelta(days=lookback_days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    end = date_to_exclusive if date_to_exclusive is not None else now
    return start, end


def ingest_snapshot(settings: Settings, *, company_id: int, date_from: datetime,
                    date_to_exclusive: datetime) -> dict:
    """Copia una ventana de respuestas y sus datos derivados a Neon.

    La escritura se hace en una transacción separada de la creación del run:
    si falla, el historial conserva el error y el último snapshot válido queda
    disponible para web y worker.
    """
    source = MySQLSourceRepository(settings)
    run_id = _create_run(settings, company_id, date_from, date_to_exclusive)
    filters = ReportFilters(
        company_id=0,
        form_id=0,
        date_from=date_from,
        date_to_exclusive=date_to_exclusive,
        evaluation_point_ids=[],
        include_all_points=True,
    )

    try:
        active_catalog = source.list_active_catalog(company_id, date_from, date_to_exclusive)
        companies = _unique_companies(active_catalog)
        forms_by_company = _forms_by_company(active_catalog)
        response_refs: list[int] = []

        # list_response_ids requiere empresa/formulario; la ingesta recorre los
        # catálogos y conserva solo las respuestas de la ventana solicitada.
        for company in companies:
            for form in forms_by_company[company.id]:
                form_filters = filters.model_copy(update={
                    "company_id": company_id,
                    "form_id": form.id,
                })
                response_refs.extend(source.list_response_ids(form_filters))

        response_ids = sorted(set(response_refs))
        _upsert_snapshot(settings, run_id, source, companies, forms_by_company, response_ids)
        _finish_run(settings, run_id, status="completed", seen=len(response_ids), upserted=len(response_ids))
        return {"run_id": str(run_id), "responses_seen": len(response_ids),
                "responses_upserted": len(response_ids), "status": "completed"}
    except Exception as exc:
        _finish_run(settings, run_id, status="failed", error_message=str(exc)[:1000])
        raise


def _create_run(settings: Settings, company_id: int, date_from: datetime, date_to_exclusive: datetime):
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO source_sync_runs (company_id, date_from, date_to_exclusive)
                   VALUES (%s, %s, %s) RETURNING id""",
                (company_id, date_from, date_to_exclusive),
            )
            run_id = cur.fetchone()["id"]
        conn.commit()
    return run_id


def _upsert_snapshot(settings, run_id, source, companies, forms_by_company, response_ids):
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            for company in companies:
                cur.execute(
                    """INSERT INTO source_catalog_companies (id, name, logo)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name,
                         logo = EXCLUDED.logo, updated_at = now()""",
                    (company.id, company.name, company.logo),
                )
                for form in forms_by_company[company.id]:
                    cur.execute(
                        """INSERT INTO source_catalog_forms (id, company_id, name, code, scale, logo)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (id) DO UPDATE SET company_id = EXCLUDED.company_id,
                             name = EXCLUDED.name, code = EXCLUDED.code, scale = EXCLUDED.scale,
                             logo = EXCLUDED.logo, updated_at = now()""",
                        (form.id, form.company_id, form.name, form.code, form.scale, form.logo),
                    )

            batch_size = settings.source_query_batch_size
            for start in range(0, len(response_ids), batch_size):
                batch = response_ids[start:start + batch_size]
                headers = source.get_response_headers(batch)
                by_id = {h.response_id: h for h in headers}
                groups = {
                    "questions": source.get_response_questions(batch),
                    "images": source.get_response_images(batch),
                    "signatures": source.get_response_signatures(batch),
                    "additional": source.get_additional_answers(batch),
                    "options": source.get_observation_options(batch),
                    "tickets": source.get_tickets(batch),
                }
                grouped = {key: _group(rows) for key, rows in groups.items()}

                for response_id in batch:
                    header = by_id.get(response_id)
                    if header is None:
                        continue
                    payload = {
                        "headers": [header.model_dump(mode="json")],
                        **{key: [row.model_dump(mode="json") for row in grouped[key].get(response_id, [])]
                           for key in grouped},
                    }
                    payload_hash = _payload_hash(payload)
                    cur.execute(
                        """INSERT INTO source_response_snapshots
                           (response_id, company_id, company_name, company_logo, form_id, form_name,
                            form_code, form_scale, form_logo, evaluation_point_id,
                            evaluation_point_name, evaluation_point_address, evaluation_point_country,
                            zone_name, completed_at, payload, payload_hash, sync_run_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (response_id) DO UPDATE SET
                             company_id = EXCLUDED.company_id, company_name = EXCLUDED.company_name,
                             company_logo = EXCLUDED.company_logo, form_id = EXCLUDED.form_id,
                             form_name = EXCLUDED.form_name, form_code = EXCLUDED.form_code,
                             form_scale = EXCLUDED.form_scale, form_logo = EXCLUDED.form_logo,
                             evaluation_point_id = EXCLUDED.evaluation_point_id,
                             evaluation_point_name = EXCLUDED.evaluation_point_name,
                             evaluation_point_address = EXCLUDED.evaluation_point_address,
                             evaluation_point_country = EXCLUDED.evaluation_point_country,
                             zone_name = EXCLUDED.zone_name, completed_at = EXCLUDED.completed_at,
                             payload = EXCLUDED.payload, payload_hash = EXCLUDED.payload_hash,
                             sync_run_id = EXCLUDED.sync_run_id, source_synced_at = now(),
                             updated_at = now()""",
                        (header.response_id, header.company_id, header.company_name, header.company_logo,
                         header.form_id, header.form_name, header.form_code, header.form_scale,
                         header.form_logo, header.evaluation_point_id, header.evaluation_point_name,
                         header.evaluation_point_address, header.evaluation_point_country,
                         header.zone_name, _naive(header.completed_at), Jsonb(payload), payload_hash, run_id),
                    )
                print(f"  snapshot: {min(start + batch_size, len(response_ids))}/{len(response_ids)}")
        conn.commit()


def _finish_run(settings, run_id, *, status: str, seen: int = 0, upserted: int = 0,
                error_message: str | None = None) -> None:
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE source_sync_runs
                   SET status = %s, responses_seen = %s, responses_upserted = %s,
                       completed_at = now(), error_message = %s
                 WHERE id = %s""",
                (status, seen, upserted, error_message, run_id),
            )
        conn.commit()


def _group(rows: list) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for row in rows:
        grouped.setdefault(row.response_id, []).append(row)
    return grouped


def _payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _naive(value):
    return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value


def _unique_companies(active_catalog):
    return list({company.id: company for company, _ in active_catalog}.values())


def _forms_by_company(active_catalog):
    result: dict[int, list] = {}
    for company, form in active_catalog:
        result.setdefault(company.id, []).append(form)
    return result
