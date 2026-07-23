"""Implementación de SourceRepository contra la base fuente (ToCheck), solo lectura.

- Conexión SSL, transacción de solo lectura y statement_timeout.
- Consultas parametrizadas cargadas desde archivos .sql (sin interpolación).
- Acepta listas de IDs por lote (ANY(%(response_ids)s)).
- No trae RUT ni correos personales innecesarios; no registra datos completos.
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from ..config import Settings
from .asset_resolver import resolve_remote_asset
from .models import (
    AdditionalAnswerRow,
    ObservationOptionRow,
    QuestionAnswerRow,
    ReportFilters,
    ResponseCount,
    ResponseHeader,
    ResponseImageRow,
    ResponseSignatureRow,
    SourceAsset,
    SourceCompany,
    SourceEvaluationPoint,
    SourceForm,
    TicketRow,
)
from .repository import SourceRepository

_QUERIES_DIR = Path(__file__).resolve().parent / "queries"


@lru_cache
def _load_sql(name: str) -> str:
    return (_QUERIES_DIR / f"{name}.sql").read_text(encoding="utf-8")


def _to_bool(value) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("1", "true", "t", "si", "sí", "yes")


class PostgresSourceRepository(SourceRepository):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._asset_base_url = None  # punto de extensión: base de imágenes de la fuente
        self._conn: psycopg.Connection | None = None

    def _connection(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            timeout_ms = self._settings.source_database_statement_timeout_seconds * 1000
            self._conn = psycopg.connect(
                self._settings.source_database_url,
                sslmode=self._settings.source_database_sslmode or "require",
                autocommit=True,
                row_factory=dict_row,
                options=f"-c statement_timeout={timeout_ms} -c default_transaction_read_only=on",
            )
        return self._conn

    def _query(self, name: str, params: dict) -> list[dict]:
        with self._connection().cursor() as cur:
            cur.execute(_load_sql(name), params)
            return cur.fetchall()

    def _batched(self, name: str, response_ids: list[int]) -> list[dict]:
        rows: list[dict] = []
        size = self._settings.source_query_batch_size
        for i in range(0, len(response_ids), size):
            rows.extend(self._query(name, {"response_ids": response_ids[i : i + size]}))
        return rows

    # ---------- catálogos ----------
    def list_companies(self) -> list[SourceCompany]:
        return [
            SourceCompany(id=r["id_empresa"], name=r["nombre_empresa"], logo=r.get("logo_empresa"))
            for r in self._query("list_companies", {})
        ]

    def list_forms(self, company_id: int) -> list[SourceForm]:
        return [
            SourceForm(
                id=r["id_formulario"], company_id=company_id, name=r["nombre_formulario"],
                code=r.get("codigo_formulario"), scale=r.get("escala_formulario"), logo=r.get("logo_formulario"),
            )
            for r in self._query("list_forms", {"company_id": company_id})
        ]

    def _filter_params(self, filters: ReportFilters) -> dict:
        return {
            "company_id": filters.company_id,
            "form_id": filters.form_id,
            "date_from": filters.date_from,
            "date_to_exclusive": filters.date_to_exclusive,
            "include_all_points": filters.include_all_points,
            "evaluation_point_ids": filters.evaluation_point_ids or [0],
        }

    def list_evaluation_points(self, filters: ReportFilters) -> list[SourceEvaluationPoint]:
        params = {
            "company_id": filters.company_id, "form_id": filters.form_id,
            "date_from": filters.date_from, "date_to_exclusive": filters.date_to_exclusive,
        }
        return [
            SourceEvaluationPoint(
                id=r["id_punto_evaluacion"], name=r.get("nombre_punto"), address=r.get("direccion_punto"),
                country=r.get("pais_punto"), zone=r.get("nombre_zona"),
            )
            for r in self._query("list_evaluation_points", params)
        ]

    def count_responses(self, filters: ReportFilters) -> ResponseCount:
        row = self._query("count_responses", self._filter_params(filters))[0]
        return ResponseCount(
            total_responses=row["total_responses"] or 0,
            total_evaluation_points=row["total_evaluation_points"] or 0,
        )

    def list_response_ids(self, filters: ReportFilters) -> list[int]:
        return [r["id_respuesta"] for r in self._query("list_response_ids", self._filter_params(filters))]

    # ---------- detalle ----------
    def get_response_headers(self, response_ids: list[int]) -> list[ResponseHeader]:
        headers = []
        for r in self._batched("response_headers", response_ids):
            headers.append(ResponseHeader(
                response_id=r["id_respuesta"], company_id=r["id_empresa"],
                company_name=r.get("nombre_empresa"), company_logo=r.get("logo_empresa"),
                form_id=r["id_formulario"], form_name=r.get("nombre_formulario"),
                form_code=r.get("codigo_formulario"), form_scale=r.get("escala_formulario"),
                form_logo=r.get("logo_formulario"),
                evaluation_point_id=r.get("id_punto_evaluacion"), evaluation_point_name=r.get("nombre_punto"),
                evaluation_point_address=r.get("direccion_punto"), evaluation_point_country=r.get("pais_punto"),
                zone_name=r.get("nombre_zona"),
                auditable_entity_id=r.get("id_entidad_auditable"), auditable_entity_name=r.get("nombre_entidad_auditable"),
                auditable_entity_code=r.get("codigo_entidad_auditable"), auditable_entity_email=r.get("correo_entidad_auditable"),
                auditable_entity_type=r.get("tipo_entidad_auditable"),
                user_id=r.get("id_usuario"), user_name=r.get("nombre_usuario"),
                user_last_name=r.get("apellido_usuario"), user_position=r.get("cargo_usuario"),
                completed_at=r["fecha_hora"], started_at=r.get("fecha_hora_inicio"),
                score=_as_float(r.get("ponderacion_total")), general_observation=r.get("observacion_general"),
                coordinates=r.get("coordenada"),
                timing=(str(r["timing"]) if r.get("timing") is not None else None),
            ))
        return headers

    def get_response_questions(self, response_ids: list[int]) -> list[QuestionAnswerRow]:
        return [
            QuestionAnswerRow(
                response_id=r["id_respuesta"], response_question_id=r["id_respuesta_pregunta"],
                question_id=r["id_pregunta"], item_id=r.get("id_item"), item_name=r.get("nombre_item"),
                item_weight=_as_float(r.get("ponderacion_item")), order=r.get("orden_pregunta"),
                statement=r.get("enunciado_pregunta") or "", question_type=r.get("tipo_pregunta"),
                answer=r.get("valor_respuesta"), score=_as_float(r.get("ponderacion_respuesta")),
                observation=r.get("observacion_respuesta"), tooltip=r.get("tooltip_pregunta"),
                requires_photo=_to_bool(r.get("requiere_foto_pregunta")),
                requires_observation=_to_bool(r.get("requiere_observacion_pregunta")),
                creates_ticket=_to_bool(r.get("genera_ticket")),
            )
            for r in self._batched("response_questions", response_ids)
        ]

    def get_response_images(self, response_ids: list[int]) -> list[ResponseImageRow]:
        return [
            ResponseImageRow(response_id=r["id_respuesta"], question_id=r.get("id_pregunta"), path=r["path"])
            for r in self._batched("response_images", response_ids) if r.get("path")
        ]

    def get_response_signatures(self, response_ids: list[int]) -> list[ResponseSignatureRow]:
        return [
            ResponseSignatureRow(
                response_id=r["id_respuesta"], signer_user_id=r.get("id_usuario_firmador"),
                signer_name=r.get("nombre_firmador"), signer_last_name=r.get("apellido_firmador"),
                status=r.get("estado_firma"), sent_at=r.get("fecha_envio_firma"),
                signed_at=r.get("fecha_firma"), observation=r.get("observacion_firma"),
            )
            for r in self._batched("response_signatures", response_ids)
        ]

    def get_additional_answers(self, response_ids: list[int]) -> list[AdditionalAnswerRow]:
        return [
            AdditionalAnswerRow(
                response_id=r["id_respuesta"], additional_question_id=r["id_pregunta_adicional"],
                question=r.get("pregunta"), question_text=r.get("pregunta_texto"),
                answer_boolean=_to_bool(r.get("respuesta_adicional_boolean")),
            )
            for r in self._batched("additional_answers", response_ids)
        ]

    def get_observation_options(self, response_ids: list[int]) -> list[ObservationOptionRow]:
        return [
            ObservationOptionRow(
                response_id=r["id_respuesta"], question_id=r.get("id_pregunta"),
                list_title=r.get("titulo_lista"),
                options=(str(r["opciones"]) if r.get("opciones") is not None else None),
            )
            for r in self._batched("observation_options", response_ids)
        ]

    def get_tickets(self, response_ids: list[int]) -> list[TicketRow]:
        return [
            TicketRow(
                response_id=r["id_respuesta"], ticket_id=r["id_ticket"],
                form_instance_id=r.get("id_formulario_instancia"), title=r.get("titulo_ticket"),
                state=r.get("ticket_estado"), priority=r.get("prioridad"), created_at=r.get("created_at"),
            )
            for r in self._batched("tickets", response_ids)
        ]

    def resolve_asset(self, path: str) -> SourceAsset:
        return resolve_remote_asset(path, asset_base_url=self._asset_base_url)


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# `datetime` importado para tipado implícito de filas (psycopg devuelve datetime).
_ = datetime
