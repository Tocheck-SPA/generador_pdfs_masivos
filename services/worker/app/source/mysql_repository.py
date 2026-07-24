"""Implementación de SourceRepository contra la base fuente de ToCheck (AWS RDS MySQL), solo lectura.

El esquema (tablas/columnas) es el mismo que documenta el spec; solo cambia el
dialecto respecto de PostgreSQL:
  - `= ANY(%(ids)s)`  ->  `IN %(ids)s`  (PyMySQL expande listas a `(a, b, c)`).
  - Timeout de sentencia vía `max_execution_time` (MySQL) en vez de `statement_timeout`.

Se reutilizan los MISMOS archivos .sql (fuente única de verdad) aplicando la
transformación de dialecto en tiempo de carga.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

from ..config import Settings
from .asset_resolver import resolve_remote_asset
from . import sql_mapping as m
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
_ANY_RE = re.compile(r"=\s*ANY\((%\(\w+\)s)\)")


@lru_cache
def _load_sql(name: str) -> str:
    raw = (_QUERIES_DIR / f"{name}.sql").read_text(encoding="utf-8")
    # `col = ANY(%(ids)s)` -> `col IN %(ids)s`  (PyMySQL añade los paréntesis al expandir la lista)
    return _ANY_RE.sub(r"IN \1", raw)


class MySQLSourceRepository(SourceRepository):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._asset_base_url = settings.source_asset_base_url or None
        self._asset_local_dir = settings.source_asset_local_dir or None
        self._conn: pymysql.connections.Connection | None = None

    def _connection(self) -> pymysql.connections.Connection:
        if self._conn is None or not self._conn.open:
            ssl = {"ssl": {}} if self._settings.source_database_use_ssl else None
            self._conn = pymysql.connect(
                host=self._settings.rds_host,
                port=self._settings.rds_port,
                user=self._settings.rds_user,
                password=self._settings.rds_pass,
                database=self._settings.rds_db,
                cursorclass=DictCursor,
                autocommit=True,
                connect_timeout=10,
                read_timeout=self._settings.source_database_statement_timeout_seconds + 10,
                charset="utf8mb4",
                ssl=ssl,
            )
            timeout_ms = self._settings.source_database_statement_timeout_seconds * 1000
            with self._conn.cursor() as cur:
                # Límite de tiempo por SELECT (MySQL 5.7.8+). Silencioso si la versión no lo soporta.
                try:
                    cur.execute("SET SESSION max_execution_time = %s", (timeout_ms,))
                except pymysql.err.MySQLError:
                    pass
        return self._conn

    def _query(self, name: str, params: dict) -> list[dict]:
        with self._connection().cursor() as cur:
            cur.execute(_load_sql(name), params)
            return cur.fetchall()

    def _batched(self, name: str, response_ids: list[int]) -> list[dict]:
        rows: list[dict] = []
        size = self._settings.source_query_batch_size
        for i in range(0, len(response_ids), size):
            chunk = response_ids[i : i + size]
            if chunk:
                rows.extend(self._query(name, {"response_ids": chunk}))
        return rows

    # ---------- catálogos ----------
    def list_companies(self) -> list[SourceCompany]:
        return [m.map_company(r) for r in self._query("list_companies", {})]

    def list_forms(self, company_id: int) -> list[SourceForm]:
        return [m.map_form(r, company_id) for r in self._query("list_forms", {"company_id": company_id})]

    def _filter_params(self, filters: ReportFilters) -> dict:
        return {
            "company_id": filters.company_id,
            "form_id": filters.form_id,
            "date_from": filters.date_from,
            "date_to_exclusive": filters.date_to_exclusive,
            "include_all_points": filters.include_all_points,
            # lista no vacía para evitar `IN ()` inválido en MySQL
            "evaluation_point_ids": filters.evaluation_point_ids or [0],
        }

    def list_evaluation_points(self, filters: ReportFilters) -> list[SourceEvaluationPoint]:
        params = {
            "company_id": filters.company_id, "form_id": filters.form_id,
            "date_from": filters.date_from, "date_to_exclusive": filters.date_to_exclusive,
        }
        return [m.map_point(r) for r in self._query("list_evaluation_points", params)]

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
        return [m.map_header(r) for r in self._batched("response_headers", response_ids)]

    def get_response_questions(self, response_ids: list[int]) -> list[QuestionAnswerRow]:
        return [m.map_question(r) for r in self._batched("response_questions", response_ids)]

    def get_response_images(self, response_ids: list[int]) -> list[ResponseImageRow]:
        return [m.map_image(r) for r in self._batched("response_images", response_ids) if r.get("path")]

    def get_response_signatures(self, response_ids: list[int]) -> list[ResponseSignatureRow]:
        return [m.map_signature(r) for r in self._batched("response_signatures", response_ids)]

    def get_additional_answers(self, response_ids: list[int]) -> list[AdditionalAnswerRow]:
        return [m.map_additional(r) for r in self._batched("additional_answers", response_ids)]

    def get_observation_options(self, response_ids: list[int]) -> list[ObservationOptionRow]:
        return [m.map_option(r) for r in self._batched("observation_options", response_ids)]

    def get_tickets(self, response_ids: list[int]) -> list[TicketRow]:
        return [m.map_ticket(r) for r in self._batched("tickets", response_ids)]

    def resolve_asset(self, path: str) -> SourceAsset:
        return resolve_remote_asset(path, asset_base_url=self._asset_base_url,
                                    local_dir=self._asset_local_dir)
