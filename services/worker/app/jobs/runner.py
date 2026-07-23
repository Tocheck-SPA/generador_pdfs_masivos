"""Loop del worker sobre Neon: reclama trabajos y los procesa de forma segura."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from ..config import Settings
from ..database import jobs as jdb
from ..database.connection import connect
from ..factories import build_email_sender, build_source_repository, build_storage
from ..logging_config import get_logger, log_context
from .processor import JobContext, process_job

_log = get_logger("jobs.runner")


def run_worker_loop(settings: Settings, *, max_iterations: int | None = None) -> None:
    repo = build_source_repository(settings)
    storage = build_storage(settings)
    email_sender = build_email_sender(settings)
    conn = connect(settings.database_url)
    iterations = 0
    try:
        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            job = jdb.claim_next_job(conn, worker_id=settings.worker_id,
                                     stale_seconds=settings.worker_stale_after_seconds)
            if job is None:
                time.sleep(settings.worker_poll_interval_seconds)
                continue
            _process_claimed(conn, job, repo=repo, storage=storage,
                             email_sender=email_sender, settings=settings)
    finally:
        conn.close()


def _process_claimed(conn, job, *, repo, storage, email_sender, settings: Settings) -> None:
    job_id = str(job["id"])
    log_context(_log, 20, "job reclamado", job_id=job_id, worker_id=settings.worker_id,
                attempt=job["attempt_count"])
    try:
        payload = jdb.load_job_payload(conn, job_id)
        ctx = JobContext(
            job_id=job_id, filters=payload["filters"], response_ids=payload["response_ids"],
            recipients=payload["recipients"], delivery_mode=job["delivery_mode"] or "auto",
            company_name=job["source_company_name"] or "", form_name=job["source_form_name"] or "",
        )

        def progress(step, processed, total, successful, failed):
            jdb.update_progress(conn, job_id, step=step, processed=processed, total=total,
                                successful=successful, failed=failed)

        def is_cancelled():
            return jdb.is_cancel_requested(conn, job_id)

        def cache_lookup(response_id, logical_key):
            return None  # la reutilización efectiva se resuelve al registrar artifacts

        email_idem = f"{job.get('idempotency_key') or job_id}:email"

        def email_guard():
            return jdb.claim_email_send(conn, job_id, email_idem, ctx.delivery_mode)

        outcome = process_job(
            ctx, repository=repo, storage=storage, email_sender=email_sender, settings=settings,
            progress=progress, cache_lookup=cache_lookup, is_cancelled=is_cancelled, email_guard=email_guard,
        )

        if outcome.status == "cancelled":
            jdb.finish_job(conn, job_id, status="cancelled", processed=len(outcome.items),
                           successful=sum(1 for i in outcome.items if i.status == "succeeded"),
                           failed=sum(1 for i in outcome.items if i.status == "failed"),
                           total_points=outcome.total_points)
            jdb.record_event(conn, job_id, level="info", event_type="cancelled",
                             message="Trabajo cancelado por el usuario.")
            return

        _persist_outcome(conn, job_id, outcome, ctx, settings, email_idem)
    except Exception as exc:  # noqa: BLE001
        log_context(_log, 40, "fallo de job", job_id=job_id, error_code="UNKNOWN_ERROR")
        jdb.record_event(conn, job_id, level="error", event_type="job_failed", message=str(exc)[:500])
        jdb.release_failed_attempt(conn, job_id, error_code="UNKNOWN_ERROR", error_message=str(exc)[:500])


def _persist_outcome(conn, job_id, outcome, ctx: JobContext, settings: Settings, email_idem: str) -> None:
    successful = sum(1 for i in outcome.items if i.status == "succeeded")
    failed = sum(1 for i in outcome.items if i.status == "failed")
    expires = datetime.now(timezone.utc) + timedelta(days=settings.report_link_expiration_days)

    for item in outcome.items:
        jdb.record_item(
            conn, job_id, item.response_id, status=item.status, payload_hash=item.payload_hash,
            error_code=item.error_code, error_message=item.error_message,
            warning_message="; ".join(item.warnings) if item.warnings else None,
        )
        if item.status == "succeeded" and item.pdf_key and item.filename:
            jdb.record_artifact(
                conn, job_id, artifact_type="pdf", filename=item.filename, storage_key=item.pdf_key,
                content_type="application/pdf", size_bytes=0, checksum="",
                source_response_id=item.response_id, source_payload_hash=item.payload_hash,
                template_version=settings.pdf_template_version, generator_version=settings.pdf_generator_version,
                expires_at=expires,
            )

    if outcome.zip_key and outcome.zip_filename:
        jdb.record_artifact(conn, job_id, artifact_type="zip", filename=outcome.zip_filename,
                            storage_key=outcome.zip_key, content_type="application/zip",
                            size_bytes=0, checksum="", expires_at=expires)
    if outcome.manifest_key:
        jdb.record_artifact(conn, job_id, artifact_type="manifest", filename="manifest.csv",
                            storage_key=outcome.manifest_key, content_type="text/csv",
                            size_bytes=0, checksum="", expires_at=expires)

    if outcome.email_result is not None:
        jdb.mark_email_result(conn, email_idem, provider=outcome.email_result.provider,
                              provider_message_id=outcome.email_result.provider_message_id,
                              status=outcome.email_result.status, total_size_bytes=0,
                              error_message=outcome.email_result.error_message)
        if outcome.email_result.status == "sent":
            jdb.mark_recipients_sent(conn, job_id, outcome.email_result.provider_message_id)

    warning = "Algunas respuestas no se pudieron procesar." if failed else None
    jdb.finish_job(conn, job_id, status=outcome.status, processed=len(outcome.items),
                   successful=successful, failed=failed, total_points=outcome.total_points,
                   warning_message=warning, error_code=outcome.error_code, error_message=outcome.error_message)
    jdb.record_event(conn, job_id, level="warning" if failed else "info", event_type="job_finished",
                     message=f"estado={outcome.status} ok={successful} fallidos={failed}")
