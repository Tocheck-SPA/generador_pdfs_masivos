"""Entrypoint del worker.

Comandos:
  python -m app.main demo    -> genera PDFs+ZIP desde fixtures a almacenamiento local (sin DB)
  python -m app.main run     -> loop que reclama trabajos de Neon y los procesa
  python -m app.main health  -> imprime estado de dependencias
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from .config import get_settings
from .factories import build_email_sender, build_source_repository, build_storage
from .jobs.processor import JobContext, process_job
from .logging_config import configure_logging, get_logger, log_context
from .source.models import ReportFilters

_log = get_logger("main")


def _demo(company_id: int, form_id: int, date_from: str, date_to_exclusive: str,
          recipients: list[str] | None = None) -> int:
    settings = get_settings()
    repo = build_source_repository(settings)
    storage = build_storage(settings)
    email = build_email_sender(settings)

    filters = ReportFilters(
        company_id=company_id, form_id=form_id,
        date_from=datetime.fromisoformat(date_from),
        date_to_exclusive=datetime.fromisoformat(date_to_exclusive),
        evaluation_point_ids=[], include_all_points=True,
    )
    response_ids = repo.list_response_ids(filters)
    count = repo.count_responses(filters)
    print(f"Se encontraron {count.total_responses} respuestas en {count.total_evaluation_points} puntos de evaluación.")
    if not response_ids:
        print("No se encontraron respuestas para los filtros seleccionados.")
        return 1

    companies = {c.id: c.name for c in repo.list_companies()}
    forms = {f.id: f.name for f in repo.list_forms(company_id)}
    ctx = JobContext(
        job_id="demo", filters=filters, response_ids=response_ids,
        recipients=recipients or ["operaciones@cliente.cl", "mantenimiento@cliente.cl"],
        delivery_mode="auto",
        company_name=companies.get(company_id, "Empresa"),
        form_name=forms.get(form_id, "Formulario"),
    )

    def progress(step: str, processed: int, total: int, ok: int, failed: int) -> None:
        label = {
            "fetching_source_data": "Preparando datos",
            "generating_pdfs": f"Generando PDF {processed} de {total}",
            "creating_bundle": "Preparando paquete",
            "uploading": "Subiendo archivos",
            "sending_email": "Enviando correo",
        }.get(step, step)
        print(f"  [{step}] {label}  (ok={ok} fallidos={failed})")

    outcome = process_job(ctx, repository=repo, storage=storage, email_sender=email,
                          settings=settings, progress=progress)

    print("\n=== RESULTADO ===")
    print(f"Estado: {outcome.status}")
    print(f"Exitosos: {sum(1 for i in outcome.items if i.status == 'succeeded')}")
    print(f"Fallidos: {sum(1 for i in outcome.items if i.status == 'failed')}")
    print(f"Puntos: {outcome.total_points}")
    if outcome.zip_key:
        print(f"ZIP: {settings.local_storage_dir}/{outcome.zip_key}")
    if outcome.email_result:
        print(f"Correo: {outcome.email_result.provider} · {outcome.email_result.status}")
    for item in outcome.items:
        flag = "OK " if item.status == "succeeded" else "ERR"
        print(f"  {flag} respuesta {item.response_id} -> {item.filename or item.error_code}"
              + (f"  [aviso] {'; '.join(item.warnings)}" if item.warnings else ""))
    return 0 if outcome.status != "failed" else 2


def _catalog(company_id: int | None, form_id: int | None, date_from: str, date_to_exclusive: str) -> int:
    """Descubre empresas / formularios / puntos contra la fuente configurada."""
    settings = get_settings()
    repo = build_source_repository(settings)
    if company_id is None:
        print("Empresas con respuestas:")
        for c in repo.list_companies():
            print(f"  {c.id:>8}  {c.name}")
        print("\nUsa --company-id <ID> para ver sus formularios.")
        return 0
    if form_id is None:
        print(f"Formularios de la empresa {company_id}:")
        for f in repo.list_forms(company_id):
            print(f"  {f.id:>8}  {f.name}  [{f.code or '-'}]")
        print("\nUsa --form-id <ID> (con --date-from/--date-to-exclusive) para ver puntos y conteo.")
        return 0
    filters = ReportFilters(
        company_id=company_id, form_id=form_id,
        date_from=datetime.fromisoformat(date_from),
        date_to_exclusive=datetime.fromisoformat(date_to_exclusive),
        evaluation_point_ids=[], include_all_points=True,
    )
    count = repo.count_responses(filters)
    print(f"Se encontraron {count.total_responses} respuestas en {count.total_evaluation_points} puntos de evaluación.")
    print("Puntos de evaluación:")
    for p in repo.list_evaluation_points(filters):
        print(f"  {p.id:>8}  {p.name}  ({p.zone or '-'})")
    return 0


def _run(max_iterations: int | None = None) -> int:
    from .jobs.runner import run_worker_loop

    settings = get_settings()
    if not settings.database_url:
        print("DATABASE_URL no está definida; el modo 'run' requiere Neon. Use 'demo' para fixtures.")
        return 1
    log_context(_log, 20, "worker iniciado", worker_id=settings.worker_id)
    run_worker_loop(settings, max_iterations=max_iterations)
    return 0


def _health() -> int:
    from .database.health import health_report

    settings = get_settings()
    print(health_report(settings))
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    configure_logging()
    parser = argparse.ArgumentParser(prog="app.main", description="ToCheck Reportes worker")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Genera PDFs+ZIP desde fixtures (sin base de datos)")
    demo.add_argument("--company-id", type=int, default=254)
    demo.add_argument("--form-id", type=int, default=100)
    demo.add_argument("--date-from", default="2026-07-01T00:00:00")
    demo.add_argument("--date-to-exclusive", default="2026-08-01T00:00:00")
    demo.add_argument("--recipients", default=None,
                      help="Correos separados por coma. Por defecto usa direcciones de prueba genéricas.")

    cat = sub.add_parser("catalog", help="Lista empresas/formularios/puntos de la fuente")
    cat.add_argument("--company-id", type=int, default=None)
    cat.add_argument("--form-id", type=int, default=None)
    cat.add_argument("--date-from", default="2026-01-01T00:00:00")
    cat.add_argument("--date-to-exclusive", default="2027-01-01T00:00:00")

    run_p = sub.add_parser("run", help="Loop de worker sobre Neon")
    run_p.add_argument("--max-iterations", type=int, default=None,
                       help="Nº de ciclos de poll antes de salir (para pruebas controladas).")
    sub.add_parser("health", help="Estado de dependencias")

    args = parser.parse_args(argv)
    if args.command == "demo":
        recipients = [r.strip() for r in args.recipients.split(",")] if args.recipients else None
        return _demo(args.company_id, args.form_id, args.date_from, args.date_to_exclusive, recipients)
    if args.command == "catalog":
        return _catalog(args.company_id, args.form_id, args.date_from, args.date_to_exclusive)
    if args.command == "run":
        return _run(args.max_iterations)
    if args.command == "health":
        return _health()
    return 1


if __name__ == "__main__":
    sys.exit(main())
