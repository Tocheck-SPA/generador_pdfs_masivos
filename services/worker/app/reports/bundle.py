"""Creación del ZIP y del manifest (CSV + JSON)."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field


@dataclass
class ManifestEntry:
    filename: str
    response_id: int
    company: str
    form: str
    point: str
    auditable_entity: str
    date: str
    status: str
    warnings: str = ""
    error: str = ""


@dataclass
class BundleResult:
    zip_bytes: bytes
    manifest_csv: bytes
    manifest_json: bytes
    included_files: list[str] = field(default_factory=list)


def _manifest_csv(entries: list[ManifestEntry]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["archivo", "id_respuesta", "empresa", "formulario", "punto",
         "entidad_auditable", "fecha", "estado", "advertencias", "error"]
    )
    for e in entries:
        writer.writerow([
            e.filename, e.response_id, e.company, e.form, e.point,
            e.auditable_entity, e.date, e.status, e.warnings, e.error,
        ])
    return buffer.getvalue().encode("utf-8-sig")  # BOM para Excel


def _manifest_json(entries: list[ManifestEntry]) -> bytes:
    payload = [e.__dict__ for e in entries]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def build_bundle(pdfs: list[tuple[str, bytes]], entries: list[ManifestEntry]) -> BundleResult:
    """`pdfs`: lista de (filename, bytes) SOLO de PDFs exitosos (no vacíos)."""
    manifest_csv = _manifest_csv(entries)
    manifest_json = _manifest_json(entries)
    buffer = io.BytesIO()
    included: list[str] = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in pdfs:
            if not content:
                continue  # nunca incluir archivos fallidos vacíos
            zf.writestr(filename, content)
            included.append(filename)
        zf.writestr("manifest.csv", manifest_csv)
        zf.writestr("manifest.json", manifest_json)
    return BundleResult(
        zip_bytes=buffer.getvalue(),
        manifest_csv=manifest_csv,
        manifest_json=manifest_json,
        included_files=included,
    )
