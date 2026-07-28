"""Render de PDF: ReportData -> Jinja2 -> HTML -> Playwright Chromium -> PDF.

No se usan coordenadas manuales; el layout es CSS de impresión.
El navegador se reutiliza entre respuestas para eficiencia.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import Browser, BrowserContext, sync_playwright

from .model import ReportData

_log = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
_DEFAULT_TOCHECK_LOGO_URL = "https://app.tocheck.cl/public/img_tocheck/logo_negro.png"

# Args inspirados en chrome-aws-lambda (sin --single-process: en Lambda suele colgar).
_CHROMIUM_ARGS = [
    "--autoplay-policy=user-gesture-required",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-client-side-phishing-detection",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-dev-shm-usage",
    "--disable-domain-reliability",
    "--disable-extensions",
    "--disable-features=AudioServiceOutOfProcess,VizDisplayCompositor",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-notifications",
    "--disable-offer-store-unmasked-wallet-cards",
    "--disable-popup-blocking",
    "--disable-print-preview",
    "--disable-prompt-on-repost",
    "--disable-renderer-backgrounding",
    "--disable-setuid-sandbox",
    "--disable-speech-api",
    "--disable-sync",
    "--disk-cache-size=33554432",
    "--font-render-hinting=none",
    "--hide-scrollbars",
    "--ignore-gpu-blocklist",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-default-browser-check",
    "--no-first-run",
    "--no-pings",
    "--no-sandbox",
    "--no-zygote",
    "--password-store=basic",
    "--use-gl=swiftshader",
    "--use-mock-keychain",
]


def _chromium_launch_args() -> list[str]:
    return list(_CHROMIUM_ARGS)


def _prepare_chromium_env() -> None:
    """Chromium necesita HOME escribible; en Lambda el default no sirve."""
    tmp = "/tmp"
    os.environ.setdefault("HOME", tmp)
    os.environ.setdefault("XDG_CONFIG_HOME", f"{tmp}/.config")
    os.environ.setdefault("XDG_CACHE_HOME", f"{tmp}/.cache")
    Path(f"{tmp}/.config").mkdir(parents=True, exist_ok=True)
    Path(f"{tmp}/.cache").mkdir(parents=True, exist_ok=True)


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


def probe_chromium() -> dict:
    """Prueba rápida de Chromium (útil vía evento Lambda debug)."""
    _prepare_chromium_env()
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(
            headless=True,
            args=_chromium_launch_args(),
            chromium_sandbox=False,
            timeout=60_000,
        )
        try:
            context = browser.new_context()
            page = context.new_page()
            page.set_content("<html><body><h1>ok</h1></body></html>", wait_until="domcontentloaded")
            pdf = page.pdf(format="A4")
            return {
                "ok": True,
                "pdfBytes": len(pdf),
                "executablePath": pw.chromium.executable_path,
            }
        finally:
            browser.close()
    finally:
        pw.stop()


class PdfRenderer:
    """Renderiza informes a PDF. Usar como context manager para reutilizar el navegador."""

    def __init__(
        self,
        template_name: str = "report.html.j2",
        render_timeout_seconds: int = 60,
        tocheck_logo_url: str = _DEFAULT_TOCHECK_LOGO_URL,
    ) -> None:
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
        self._tocheck_logo_url = tocheck_logo_url
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> "PdfRenderer":
        # Launch perezoso en el primer render_pdf (evita proceso muerto durante fetches).
        return self

    def __exit__(self, *exc) -> None:
        self._close_browser()

    def _ensure_browser(self) -> None:
        if self._browser is not None and self._browser.is_connected() and self._context is not None:
            return
        self._close_browser()
        _prepare_chromium_env()
        self._pw = sync_playwright().start()
        _log.info(
            "chromium launch executable=%s",
            self._pw.chromium.executable_path,
        )
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=_chromium_launch_args(),
            chromium_sandbox=False,
            handle_sighup=False,
            handle_sigint=False,
            handle_sigterm=False,
            timeout=60_000,
        )
        self._context = self._browser.new_context()
        # Smoke test inmediato: si Chromium muere al crear páginas, fallar acá.
        page = self._context.new_page()
        page.close()

    def _close_browser(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:  # noqa: BLE001
                pass
            self._context = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:  # noqa: BLE001
                pass
            self._browser = None
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:  # noqa: BLE001
                pass
            self._pw = None

    def render_html(self, data: ReportData) -> str:
        return self._template.render(r=data, tocheck_logo_url=self._tocheck_logo_url)

    def render_pdf(self, data: ReportData) -> bytes:
        self._ensure_browser()
        assert self._context is not None
        html = self.render_html(data)
        try:
            page = self._context.new_page()
        except Exception:
            self._close_browser()
            self._ensure_browser()
            assert self._context is not None
            page = self._context.new_page()
        try:
            page.set_default_timeout(self._timeout_ms)
            page.set_content(html, wait_until="domcontentloaded")
            return page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"},
            )
        finally:
            page.close()
