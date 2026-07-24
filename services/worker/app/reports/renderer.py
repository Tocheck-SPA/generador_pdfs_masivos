"""Render de PDF: ReportData -> Jinja2 -> HTML -> Playwright Chromium -> PDF.

No se usan coordenadas manuales; el layout es CSS de impresión.
El navegador se reutiliza entre respuestas para eficiencia.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from .model import ReportData

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fmt_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return f"{value.day:02d}-{value.month:02d}-{value.year} {value.hour:02d}:{value.minute:02d}"


def _fmt_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return f"{value.day} de {_MONTHS_ES[value.month - 1]} de {value.year}"


def _fmt_score(value: float | None) -> str:
    if value is None:
        return "—"
    if float(value).is_integer():
        return f"{int(value)}"
    return f"{value:.1f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return f"{int(rounded)}%"
    text = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


class PdfRenderer:
    """Renderiza informes a PDF. Usar como context manager para reutilizar el navegador."""

    def __init__(self, template_name: str = "report.html.j2", render_timeout_seconds: int = 60) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
        )
        self._env.filters["fmt_datetime"] = _fmt_datetime
        self._env.filters["fmt_date"] = _fmt_date
        self._env.filters["fmt_score"] = _fmt_score
        self._env.filters["fmt_pct"] = _fmt_pct
        self._template = self._env.get_template(template_name)
        self._timeout_ms = render_timeout_seconds * 1000
        self._pw = None
        self._browser = None

    def __enter__(self) -> "PdfRenderer":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        return self

    def __exit__(self, *exc) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def render_html(self, data: ReportData) -> str:
        return self._template.render(r=data)

    def render_pdf(self, data: ReportData) -> bytes:
        if self._browser is None:
            raise RuntimeError("PdfRenderer debe usarse como context manager (with PdfRenderer() as ...).")
        html = self.render_html(data)
        page = self._browser.new_page()
        try:
            page.set_default_timeout(self._timeout_ms)
            page.set_content(html, wait_until="networkidle")
            return page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"},
            )
        finally:
            page.close()
