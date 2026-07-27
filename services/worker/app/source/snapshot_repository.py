"""Repositorio de la fuente a partir del snapshot diario almacenado en Neon."""
from __future__ import annotations

import json

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


class SnapshotSourceRepository(SourceRepository):
    """Lee únicamente la información de fuente ya ingerida en Neon."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._conn: psycopg.Connection | None = None

    def _connection(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(
                self._settings.database_url,
                sslmode="require",
                autocommit=True,
                row_factory=dict_row,
            )
        return self._conn

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._connection().cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def list_companies(self) -> list[SourceCompany]:
        return [SourceCompany(id=r["id"], name=r["name"], logo=r["logo"])
                for r in self._query("SELECT id, name, logo FROM source_catalog_companies ORDER BY name")]

    def list_forms(self, company_id: int) -> list[SourceForm]:
        return [SourceForm(id=r["id"], company_id=r["company_id"], name=r["name"],
                           code=r["code"], scale=r["scale"], logo=r["logo"])
                for r in self._query(
                    "SELECT id, company_id, name, code, scale, logo "
                    "FROM source_catalog_forms WHERE company_id = %s ORDER BY name",
                    (company_id,),
                )]

    def list_evaluation_points(self, filters: ReportFilters) -> list[SourceEvaluationPoint]:
        return [SourceEvaluationPoint(
                    id=r["evaluation_point_id"], name=r["evaluation_point_name"],
                    address=r["evaluation_point_address"], country=r["evaluation_point_country"],
                    zone=r["zone_name"],
                ) for r in self._query(
                    """SELECT DISTINCT evaluation_point_id, evaluation_point_name,
                              evaluation_point_address, evaluation_point_country, zone_name
                         FROM source_response_snapshots
                        WHERE company_id = %s AND form_id = %s
                          AND completed_at >= %s AND completed_at < %s
                          AND evaluation_point_id IS NOT NULL
                        ORDER BY evaluation_point_name""",
                    (filters.company_id, filters.form_id, _naive(filters.date_from),
                     _naive(filters.date_to_exclusive)),
                )]

    def _where(self, filters: ReportFilters) -> tuple[str, list]:
        clauses = ["company_id = %s", "form_id = %s", "completed_at >= %s", "completed_at < %s"]
        # La fuente MySQL entrega fechas sin zona horaria. Conservamos esa
        # semántica para que un filtro por día no cambie de fecha en Neon.
        params: list = [filters.company_id, filters.form_id, _naive(filters.date_from),
                        _naive(filters.date_to_exclusive)]
        if not filters.include_all_points and filters.evaluation_point_ids:
            clauses.append("evaluation_point_id = ANY(%s)")
            params.append(filters.evaluation_point_ids)
        return " AND ".join(clauses), params

    def count_responses(self, filters: ReportFilters) -> ResponseCount:
        where, params = self._where(filters)
        row = self._query(
            f"SELECT COUNT(*) AS total_responses, COUNT(DISTINCT evaluation_point_id) "
            f"AS total_evaluation_points FROM source_response_snapshots WHERE {where}",
            tuple(params),
        )[0]
        return ResponseCount(total_responses=row["total_responses"] or 0,
                             total_evaluation_points=row["total_evaluation_points"] or 0)

    def list_response_ids(self, filters: ReportFilters) -> list[int]:
        where, params = self._where(filters)
        rows = self._query(
            f"SELECT response_id FROM source_response_snapshots WHERE {where} "
            "ORDER BY completed_at, response_id", tuple(params),
        )
        return [r["response_id"] for r in rows]

    def _payload_rows(self, response_ids: list[int], key: str) -> list[dict]:
        if not response_ids:
            return []
        rows = self._query(
            "SELECT payload FROM source_response_snapshots WHERE response_id = ANY(%s)",
            (response_ids,),
        )
        output: list[dict] = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            output.extend(payload.get(key, []))
        return output

    def get_response_headers(self, response_ids: list[int]) -> list[ResponseHeader]:
        return [ResponseHeader.model_validate(r) for r in self._payload_rows(response_ids, "headers")]

    def get_response_questions(self, response_ids: list[int]) -> list[QuestionAnswerRow]:
        return [QuestionAnswerRow.model_validate(r) for r in self._payload_rows(response_ids, "questions")]

    def get_response_images(self, response_ids: list[int]) -> list[ResponseImageRow]:
        return [ResponseImageRow.model_validate(r) for r in self._payload_rows(response_ids, "images")]

    def get_response_signatures(self, response_ids: list[int]) -> list[ResponseSignatureRow]:
        return [ResponseSignatureRow.model_validate(r) for r in self._payload_rows(response_ids, "signatures")]

    def get_additional_answers(self, response_ids: list[int]) -> list[AdditionalAnswerRow]:
        return [AdditionalAnswerRow.model_validate(r) for r in self._payload_rows(response_ids, "additional")]

    def get_observation_options(self, response_ids: list[int]) -> list[ObservationOptionRow]:
        return [ObservationOptionRow.model_validate(r) for r in self._payload_rows(response_ids, "options")]

    def get_tickets(self, response_ids: list[int]) -> list[TicketRow]:
        return [TicketRow.model_validate(r) for r in self._payload_rows(response_ids, "tickets")]

    def resolve_asset(self, path: str) -> SourceAsset:
        return resolve_remote_asset(path, asset_base_url=self._settings.source_asset_base_url,
                                    local_dir=self._settings.source_asset_local_dir or None)


def _naive(value):
    return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value
