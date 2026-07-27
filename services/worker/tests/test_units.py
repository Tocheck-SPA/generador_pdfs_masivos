from __future__ import annotations

import io
import zipfile
from datetime import datetime

from app.reports.bundle import ManifestEntry, build_bundle
from app.reports.filenames import pdf_filename, slugify, zip_filename
from app.reports.observation_options import parse_observation_options


# ---------- observation options ----------
def test_parse_options_plain_text():
    assert parse_observation_options("Ninguna") == ["Ninguna"]


def test_parse_options_json_list():
    assert parse_observation_options('["A", "B"]') == ["A", "B"]


def test_parse_options_comma():
    assert parse_observation_options("A, B, C") == ["A", "B", "C"]


def test_parse_options_empty():
    assert parse_observation_options(None) == []
    assert parse_observation_options("   ") == []


# ---------- filenames ----------
def test_slugify_strips_accents_and_spaces():
    assert slugify("Sucursal Providencia Ñuñoa") == "sucursal_providencia_nunoa"


def test_pdf_filename_point_only():
    name = pdf_filename(datetime(2026, 7, 22), "Tarragona Retail", "Providencia", None, "Preventiva", 128483)
    assert name == "2026-07-22_tarragona_retail_providencia_preventiva_128483.pdf"
    assert name.endswith("_128483.pdf")


def test_pdf_filename_with_entity():
    name = pdf_filename(datetime(2026, 7, 4), "BeLive", "Movistar Arena",
                        "FRANK COMPLETERIA-FM11", "BPM Foodtruck 1.1", 446748)
    assert name == "2026-07-04_belive_movistar_arena_frank_completeria_fm11_bpm_foodtruck_1_1_446748.pdf"


def test_pdf_filename_entity_only():
    name = pdf_filename(datetime(2026, 7, 4), "BeLive", None, "Camión ABCD-12", "Auditoría", 500)
    assert name == "2026-07-04_belive_camion_abcd_12_auditoria_500.pdf"


def test_pdf_filename_neither_point_nor_entity():
    # Sin punto ni entidad: no se agregan segmentos vacíos.
    name = pdf_filename(datetime(2026, 7, 4), "BeLive", None, None, "Auditoría", 500)
    assert name == "2026-07-04_belive_auditoria_500.pdf"


def test_zip_filename():
    name = zip_filename("Tarragona", datetime(2026, 7, 1), datetime(2026, 7, 31))
    assert name == "informes_tarragona_2026-07-01_2026-07-31.zip"


# ---------- bundle ----------
def test_bundle_includes_manifest_and_skips_empty():
    entries = [
        ManifestEntry("a.pdf", 1, "Emp", "Form", "P", "", "2026-07-01 10:00", "ok"),
        ManifestEntry("", 2, "Emp", "Form", "P", "", "2026-07-01 10:00", "error", error="boom"),
    ]
    pdfs = [("a.pdf", b"%PDF-1.4 data"), ("empty.pdf", b"")]
    result = build_bundle(pdfs, entries)
    zf = zipfile.ZipFile(io.BytesIO(result.zip_bytes))
    names = zf.namelist()
    assert "a.pdf" in names
    assert "empty.pdf" not in names  # nunca incluir archivos vacíos
    assert "manifest.csv" in names and "manifest.json" in names


# ---------- attachment decision ----------
def test_attachment_decision():
    from app.jobs.processor import _decide_attachment

    small = b"x" * 1000
    big = b"x" * 30_000_000
    assert _decide_attachment("attachments", "f.zip", big, 25_000_000) is not None  # forzado
    assert _decide_attachment("download_link", "f.zip", small, 25_000_000) is None  # forzado enlace
    assert _decide_attachment("auto", "f.zip", small, 25_000_000) is not None  # cabe -> adjunto
    assert _decide_attachment("auto", "f.zip", big, 25_000_000) is None  # muy grande -> enlace
