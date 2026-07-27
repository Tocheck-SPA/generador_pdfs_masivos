"""AWS Lambda entrypoint for the provider-neutral report worker."""
from __future__ import annotations

from uuid import UUID

from .config import get_settings
from .jobs.runner import run_worker_job


def handler(event: dict, context) -> dict:
    if not isinstance(event, dict) or event.get("schemaVersion") != 1:
        raise ValueError("Evento Lambda inválido: schemaVersion debe ser 1")
    raw_job_id = event.get("jobId")
    if not isinstance(raw_job_id, str):
        raise ValueError("Evento Lambda inválido: falta jobId")
    try:
        job_id = str(UUID(raw_job_id))
    except ValueError as exc:
        raise ValueError("Evento Lambda inválido: jobId no es UUID") from exc

    settings = get_settings()
    request_id = getattr(context, "aws_request_id", None)
    processed = run_worker_job(
        settings,
        job_id,
        worker_id=f"lambda:{request_id}" if request_id else None,
    )
    return {"schemaVersion": 1, "jobId": job_id, "processed": processed}
