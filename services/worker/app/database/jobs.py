"""Operaciones sobre la cola de trabajos en Neon.

Incluye el claim atómico (FOR UPDATE SKIP LOCKED), heartbeat, progreso,
recuperación de trabajos abandonados e idempotencia de correo.
"""
from __future__ import annotations

import json
from datetime import datetime

import psycopg

from ..source.models import ReportFilters

_ACTIVE_STATES = (
    "processing", "fetching_source_data", "generating_pdfs",
    "creating_bundle", "uploading", "sending_email",
)
_TERMINAL_STATES = ("completed", "completed_with_warnings", "failed", "cancelled")

# El claim recupera pendientes y también procesos con heartbeat vencido (stale),
# siempre que no se haya superado max_attempts, no estén en estado terminal y no
# tengan un correo ya enviado. Nunca dos workers envían el mismo correo.
_CLAIM_SQL = """
WITH claimable AS (
    SELECT id
    FROM report_jobs
    WHERE attempt_count < max_attempts
      AND status <> ALL(%(terminal)s)
      AND cancelled_at IS NULL
      AND (
            status = 'pending'
            OR (status = ANY(%(active)s)
                AND (heartbeat_at IS NULL
                     OR heartbeat_at < now() - make_interval(secs => %(stale_seconds)s)))
      )
      AND NOT EXISTS (
            SELECT 1 FROM email_deliveries ed
            WHERE ed.job_id = report_jobs.id AND ed.status = 'sent'
      )
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE report_jobs j
SET status = 'processing',
    locked_by = %(worker_id)s,
    locked_at = now(),
    heartbeat_at = now(),
    started_at = COALESCE(j.started_at, now()),
    attempt_count = j.attempt_count + 1,
    updated_at = now()
FROM claimable c
WHERE j.id = c.id
RETURNING j.*;
"""


def claim_next_job(conn: psycopg.Connection, *, worker_id: str, stale_seconds: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(_CLAIM_SQL, {
            "worker_id": worker_id, "stale_seconds": stale_seconds,
            "active": list(_ACTIVE_STATES), "terminal": list(_TERMINAL_STATES),
        })
        row = cur.fetchone()
    conn.commit()
    return row


def load_job_payload(conn: psycopg.Connection, job_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM report_jobs WHERE id = %s", (job_id,))
        job = cur.fetchone()
        cur.execute(
            "SELECT source_response_id FROM report_job_items WHERE job_id = %s ORDER BY source_response_date, source_response_id",
            (job_id,),
        )
        response_ids = [r["source_response_id"] for r in cur.fetchall()]
        cur.execute("SELECT email FROM report_job_recipients WHERE job_id = %s", (job_id,))
        recipients = [r["email"] for r in cur.fetchall()]
    filters = ReportFilters(
        company_id=job["source_company_id"], form_id=job["source_form_id"],
        date_from=job["date_from"], date_to_exclusive=job["date_to_exclusive"],
        evaluation_point_ids=(job["filters"] or {}).get("evaluationPointIds", []),
        include_all_points=(job["filters"] or {}).get("includeAllPoints", True),
    )
    return {"job": job, "filters": filters, "response_ids": response_ids, "recipients": recipients}


def heartbeat(conn: psycopg.Connection, job_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE report_jobs SET heartbeat_at = now(), updated_at = now() WHERE id = %s", (job_id,))
    conn.commit()


def update_progress(conn: psycopg.Connection, job_id: str, *, step: str, processed: int,
                    total: int, successful: int, failed: int) -> None:
    percent = int(processed * 100 / total) if total else 0
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE report_jobs
               SET status = %s, current_step = %s, processed_responses = %s,
                   successful_responses = %s, failed_responses = %s,
                   progress_percent = GREATEST(progress_percent, %s),
                   heartbeat_at = now(), updated_at = now()
               WHERE id = %s""",
            (step, step, processed, successful, failed, percent, job_id),
        )
    conn.commit()


def is_cancel_requested(conn: psycopg.Connection, job_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT status, cancelled_at FROM report_jobs WHERE id = %s", (job_id,))
        row = cur.fetchone()
    return bool(row) and (row["status"] == "cancel_requested" or row["cancelled_at"] is not None)


def record_event(conn: psycopg.Connection, job_id: str, *, level: str, event_type: str,
                 message: str | None = None, response_id: int | None = None, metadata: dict | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO report_events (job_id, source_response_id, level, event_type, message, metadata)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (job_id, response_id, level, event_type, message, json.dumps(metadata or {})),
        )
    conn.commit()


def record_item(conn: psycopg.Connection, job_id: str, response_id: int, *, status: str,
                payload_hash: str | None = None, error_code: str | None = None,
                error_message: str | None = None, warning_message: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE report_job_items
               SET status = %s, source_payload_hash = %s, error_code = %s, error_message = %s,
                   warning_message = %s, completed_at = now(), updated_at = now(),
                   attempt_count = attempt_count + 1
               WHERE job_id = %s AND source_response_id = %s""",
            (status, payload_hash, error_code, error_message, warning_message, job_id, response_id),
        )
    conn.commit()


def record_artifact(conn: psycopg.Connection, job_id: str, *, artifact_type: str, filename: str,
                    storage_key: str, content_type: str, size_bytes: int, checksum: str,
                    source_response_id: int | None = None, source_payload_hash: str | None = None,
                    template_version: str | None = None, generator_version: str | None = None,
                    expires_at: datetime | None = None) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO report_artifacts
               (job_id, source_response_id, artifact_type, filename, storage_key, content_type,
                size_bytes, checksum, source_payload_hash, template_version, generator_version, expires_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (job_id, source_response_id, artifact_type, filename, storage_key, content_type,
             size_bytes, checksum, source_payload_hash, template_version, generator_version, expires_at),
        )
        artifact_id = cur.fetchone()["id"]
    conn.commit()
    return str(artifact_id)


def cache_lookup(conn: psycopg.Connection, response_id: int, logical_key: str,
                 template_version: str, generator_version: str, payload_hash: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT storage_key FROM report_artifacts
               WHERE source_response_id = %s AND source_payload_hash = %s
                 AND template_version = %s AND generator_version = %s AND artifact_type = 'pdf'
               ORDER BY created_at DESC LIMIT 1""",
            (response_id, payload_hash, template_version, generator_version),
        )
        row = cur.fetchone()
    return row["storage_key"] if row else None


def email_already_sent(conn: psycopg.Connection, job_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM email_deliveries WHERE job_id = %s AND status = 'sent'", (job_id,))
        return cur.fetchone() is not None


def record_email_delivery(conn: psycopg.Connection, job_id: str, *, idempotency_key: str, provider: str,
                          provider_message_id: str | None, delivery_mode: str, total_size_bytes: int,
                          status: str, error_message: str | None = None) -> bool:
    """Inserta la entrega de forma idempotente. Devuelve True si se insertó (no existía)."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO email_deliveries
               (job_id, provider, provider_message_id, delivery_mode, total_size_bytes, status,
                idempotency_key, sent_at, error_message)
               VALUES (%s,%s,%s,%s,%s,%s,%s, CASE WHEN %s = 'sent' THEN now() ELSE NULL END, %s)
               ON CONFLICT (idempotency_key) DO NOTHING
               RETURNING id""",
            (job_id, provider, provider_message_id, delivery_mode, total_size_bytes, status,
             idempotency_key, status, error_message),
        )
        inserted = cur.fetchone() is not None
    conn.commit()
    return inserted


def claim_email_send(conn: psycopg.Connection, job_id: str, idempotency_key: str, delivery_mode: str) -> bool:
    """Reclama el derecho a enviar el correo del job de forma atómica.

    Inserta una fila 'sending' con clave de idempotencia. Devuelve True solo si
    ESTE worker la insertó (nadie más envió/está enviando). Evita doble envío.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM email_deliveries WHERE job_id = %s AND status = 'sent'", (job_id,))
        if cur.fetchone() is not None:
            conn.commit()
            return False
        cur.execute(
            """INSERT INTO email_deliveries (job_id, provider, delivery_mode, status, idempotency_key)
               VALUES (%s, %s, %s, 'sending', %s)
               ON CONFLICT (idempotency_key) DO NOTHING
               RETURNING id""",
            (job_id, "pending", delivery_mode, idempotency_key),
        )
        inserted = cur.fetchone() is not None
    conn.commit()
    return inserted


def mark_email_result(conn: psycopg.Connection, idempotency_key: str, *, provider: str,
                      provider_message_id: str | None, status: str, total_size_bytes: int,
                      error_message: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE email_deliveries
               SET provider = %s, provider_message_id = %s, status = %s, total_size_bytes = %s,
                   error_message = %s, sent_at = CASE WHEN %s = 'sent' THEN now() ELSE sent_at END
               WHERE idempotency_key = %s""",
            (provider, provider_message_id, status, total_size_bytes, error_message, status, idempotency_key),
        )
    conn.commit()


def mark_recipients_sent(conn: psycopg.Connection, job_id: str, provider_message_id: str | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE report_job_recipients
               SET delivery_status = 'sent', provider_message_id = %s, delivered_at = now()
               WHERE job_id = %s""",
            (provider_message_id, job_id),
        )
    conn.commit()


def finish_job(conn: psycopg.Connection, job_id: str, *, status: str, processed: int, successful: int,
               failed: int, total_points: int, warning_message: str | None = None,
               error_code: str | None = None, error_message: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE report_jobs
               SET status = %s, processed_responses = %s, successful_responses = %s,
                   failed_responses = %s, progress_percent = 100, current_step = %s,
                   warning_message = %s, error_code = %s, error_message = %s,
                   completed_at = now(), updated_at = now()
               WHERE id = %s""",
            (status, processed, successful, failed, status, warning_message, error_code, error_message, job_id),
        )
    conn.commit()


def release_failed_attempt(conn: psycopg.Connection, job_id: str, *, error_code: str, error_message: str) -> None:
    """Marca el intento como fallido dejando el job reintetable si quedan intentos."""
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE report_jobs
               SET status = CASE WHEN attempt_count >= max_attempts THEN 'failed' ELSE 'pending' END,
                   error_code = %s, error_message = %s, locked_by = NULL, updated_at = now(),
                   completed_at = CASE WHEN attempt_count >= max_attempts THEN now() ELSE NULL END
               WHERE id = %s""",
            (error_code, error_message, job_id),
        )
    conn.commit()
