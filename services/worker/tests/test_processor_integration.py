from __future__ import annotations

import io
import zipfile

import pypdf

from app.email.console_email import ConsoleEmailSender
from app.factories import build_source_repository, build_storage
from app.jobs.processor import JobContext, process_job


def _ctx(response_ids, delivery_mode="auto"):
    from datetime import datetime

    from app.source.models import ReportFilters

    return JobContext(
        job_id="test", filters=ReportFilters(
            company_id=254, form_id=100,
            date_from=datetime(2026, 7, 1), date_to_exclusive=datetime(2026, 8, 1),
        ),
        response_ids=response_ids, recipients=["a@x.cl", "b@y.cl"],
        delivery_mode=delivery_mode, company_name="Tarragona Retail", form_name="Inspección Preventiva",
    )


def test_process_job_end_to_end(settings):
    repo = build_source_repository(settings)
    storage = build_storage(settings)
    email = ConsoleEmailSender()
    ctx = _ctx([128483, 128485, 128490])

    outcome = process_job(ctx, repository=repo, storage=storage, email_sender=email, settings=settings)

    assert outcome.status in ("completed", "completed_with_warnings")
    assert sum(1 for i in outcome.items if i.status == "succeeded") == 3
    assert outcome.zip_key and storage.exists(outcome.zip_key)
    assert outcome.email_result and outcome.email_result.status == "sent"

    # El ZIP contiene 3 PDFs + manifest.csv + manifest.json
    zip_path = settings.local_storage_dir + "/" + outcome.zip_key
    with open(zip_path, "rb") as fh:
        zf = zipfile.ZipFile(io.BytesIO(fh.read()))
    names = zf.namelist()
    assert sum(1 for n in names if n.endswith(".pdf")) == 3
    assert "manifest.csv" in names and "manifest.json" in names

    # Un PDF real: no vacío, con texto e ID de respuesta.
    pdf_name = next(n for n in names if "128483" in n)
    reader = pypdf.PdfReader(io.BytesIO(zf.read(pdf_name)))
    assert len(reader.pages) >= 1
    text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "128483" in text
    assert "Preventiva" in text


def test_completed_with_warnings_on_partial_failure(settings):
    repo = build_source_repository(settings)
    storage = build_storage(settings)
    email = ConsoleEmailSender()
    # 999999 no existe -> item fallido; el resto ok -> completed_with_warnings.
    ctx = _ctx([128483, 999999])
    outcome = process_job(ctx, repository=repo, storage=storage, email_sender=email, settings=settings)
    assert outcome.status == "completed_with_warnings"
    assert any(i.status == "failed" for i in outcome.items)
    assert any(i.status == "succeeded" for i in outcome.items)


def test_all_failures_produce_failed_and_no_bundle(settings):
    repo = build_source_repository(settings)
    storage = build_storage(settings)
    email = ConsoleEmailSender()
    ctx = _ctx([999998, 999999])
    outcome = process_job(ctx, repository=repo, storage=storage, email_sender=email, settings=settings)
    assert outcome.status == "failed"
    assert outcome.zip_key is None
    assert outcome.email_result is None  # no se envía paquete vacío


def test_email_guard_blocks_second_send(settings):
    repo = build_source_repository(settings)
    storage = build_storage(settings)
    email = ConsoleEmailSender()
    ctx = _ctx([128483])
    calls = {"n": 0}

    def guard():
        calls["n"] += 1
        return calls["n"] == 1  # solo el primer intento puede enviar

    o1 = process_job(ctx, repository=repo, storage=storage, email_sender=email, settings=settings, email_guard=guard)
    o2 = process_job(ctx, repository=repo, storage=storage, email_sender=email, settings=settings, email_guard=guard)
    assert o1.email_result is not None
    assert o2.email_result is None  # el guard evitó el segundo envío


def test_delivery_link_mode_no_attachment(settings):
    repo = build_source_repository(settings)
    storage = build_storage(settings)
    email = ConsoleEmailSender()
    ctx = _ctx([128483], delivery_mode="download_link")
    outcome = process_job(ctx, repository=repo, storage=storage, email_sender=email, settings=settings)
    assert outcome.download_url is not None
