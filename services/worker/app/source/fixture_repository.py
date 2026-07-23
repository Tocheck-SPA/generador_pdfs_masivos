"""Implementación de SourceRepository basada en fixtures JSON del repo.

Permite ejecutar y probar todo el pipeline sin conexión a producción.
Lee los mismos archivos que consume el frontend (carpeta /fixtures).
"""
from __future__ import annotations

import json
import mimetypes
from datetime import datetime
from pathlib import Path

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


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class FixtureSourceRepository(SourceRepository):
    def __init__(self, fixtures_dir: str | Path) -> None:
        self._dir = Path(fixtures_dir)
        self._cache: dict[str, list[dict]] = {}

    def _load(self, name: str) -> list[dict]:
        if name not in self._cache:
            path = self._dir / f"{name}.json"
            self._cache[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        return self._cache[name]

    # ---------- catálogos ----------
    def list_companies(self) -> list[SourceCompany]:
        return [SourceCompany(id=c["id"], name=c["name"], logo=c.get("logo")) for c in self._load("companies")]

    def list_forms(self, company_id: int) -> list[SourceForm]:
        forms = [f for f in self._load("forms") if f["companyId"] == company_id]
        # solo formularios con respuestas
        with_responses = {r["formId"] for r in self._load("responses") if r["companyId"] == company_id}
        return [
            SourceForm(
                id=f["id"], company_id=f["companyId"], name=f["name"], code=f.get("code"),
                scale=f.get("scale"), logo=f.get("logo"), welcome_message=f.get("welcomeMessage"),
            )
            for f in forms if f["id"] in with_responses
        ]

    def _matching_responses(self, filters: ReportFilters) -> list[dict]:
        out = []
        for r in self._load("responses"):
            if r["companyId"] != filters.company_id or r["formId"] != filters.form_id:
                continue
            completed = _parse_dt(r["completedAt"])
            if completed is None or completed < filters.date_from or completed >= filters.date_to_exclusive:
                continue
            if not filters.include_all_points and filters.evaluation_point_ids:
                if r.get("evaluationPointId") not in filters.evaluation_point_ids:
                    continue
            out.append(r)
        return out

    def list_evaluation_points(self, filters: ReportFilters) -> list[SourceEvaluationPoint]:
        point_ids = {r["evaluationPointId"] for r in self._matching_responses(filters) if r.get("evaluationPointId")}
        points = {}
        for p in self._load("evaluation_points"):
            if p["companyId"] == filters.company_id and p["formId"] == filters.form_id and p["id"] in point_ids:
                points[p["id"]] = p
        return [
            SourceEvaluationPoint(
                id=p["id"], name=p.get("name"), address=p.get("address"), country=p.get("country"),
                zone=p.get("zone"), latitude=p.get("lat"), longitude=p.get("long"),
            )
            for p in sorted(points.values(), key=lambda x: (x.get("name") or ""))
        ]

    def count_responses(self, filters: ReportFilters) -> ResponseCount:
        matching = self._matching_responses(filters)
        points = {r.get("evaluationPointId") for r in matching if r.get("evaluationPointId")}
        return ResponseCount(total_responses=len(matching), total_evaluation_points=len(points))

    def list_response_ids(self, filters: ReportFilters) -> list[int]:
        matching = sorted(self._matching_responses(filters), key=lambda r: (r["completedAt"], r["responseId"]))
        return [r["responseId"] for r in matching]

    # ---------- detalle por respuesta ----------
    def get_response_headers(self, response_ids: list[int]) -> list[ResponseHeader]:
        ids = set(response_ids)
        companies = {c["id"]: c for c in self._load("companies")}
        forms = {f["id"]: f for f in self._load("forms")}
        points = {(p["id"], p["formId"]): p for p in self._load("evaluation_points")}
        points_by_id = {p["id"]: p for p in self._load("evaluation_points")}
        entities = {e["id"]: e for e in self._load("auditable_entities")}
        users = {u["id"]: u for u in self._load("users")}
        headers = []
        for r in self._load("responses"):
            if r["responseId"] not in ids:
                continue
            company = companies.get(r["companyId"], {})
            form = forms.get(r["formId"], {})
            point = points.get((r.get("evaluationPointId"), r["formId"])) or points_by_id.get(r.get("evaluationPointId"), {})
            entity = entities.get(r.get("auditableEntityId"), {})
            user = users.get(r.get("userId"), {})
            headers.append(ResponseHeader(
                response_id=r["responseId"], company_id=r["companyId"],
                company_name=company.get("name"), company_logo=company.get("logo"),
                form_id=r["formId"], form_name=form.get("name"), form_code=form.get("code"),
                form_scale=form.get("scale"), form_logo=form.get("logo"),
                evaluation_point_id=r.get("evaluationPointId"),
                evaluation_point_name=point.get("name"), evaluation_point_address=point.get("address"),
                evaluation_point_country=point.get("country"), zone_name=point.get("zone"),
                auditable_entity_id=r.get("auditableEntityId"), auditable_entity_name=entity.get("name"),
                auditable_entity_code=entity.get("identifierCode"), auditable_entity_email=entity.get("email"),
                auditable_entity_type=entity.get("type"),
                user_id=r.get("userId"), user_name=user.get("names"), user_last_name=user.get("lastNames"),
                user_position=user.get("position"),
                completed_at=_parse_dt(r["completedAt"]), started_at=_parse_dt(r.get("startedAt")),
                score=r.get("score"), general_observation=r.get("generalObservation"),
                coordinates=r.get("coordinates"), timing=(str(r["timing"]) if r.get("timing") is not None else None),
            ))
        return headers

    def get_response_questions(self, response_ids: list[int]) -> list[QuestionAnswerRow]:
        ids = set(response_ids)
        return [
            QuestionAnswerRow(
                response_id=q["responseId"], response_question_id=q["responseQuestionId"],
                question_id=q["questionId"], item_id=q.get("itemId"), item_name=q.get("itemName"),
                item_weight=q.get("itemWeight"), order=q.get("order"), statement=q["statement"],
                question_type=q.get("questionType"), answer=q.get("answer"), score=q.get("score"),
                observation=q.get("observation"), tooltip=q.get("tooltip"),
                requires_photo=q.get("requiresPhoto"), requires_observation=q.get("requiresObservation"),
                creates_ticket=q.get("createsTicket"),
            )
            for q in self._load("questions") if q["responseId"] in ids
        ]

    def get_response_images(self, response_ids: list[int]) -> list[ResponseImageRow]:
        ids = set(response_ids)
        return [
            ResponseImageRow(response_id=i["responseId"], question_id=i.get("questionId"), path=i["path"])
            for i in self._load("images") if i["responseId"] in ids
        ]

    def get_response_signatures(self, response_ids: list[int]) -> list[ResponseSignatureRow]:
        ids = set(response_ids)
        return [
            ResponseSignatureRow(
                response_id=s["responseId"], signer_user_id=s.get("signerUserId"),
                signer_name=s.get("signerName"), signer_last_name=s.get("signerLastName"),
                status=s.get("status"), sent_at=_parse_dt(s.get("sentAt")),
                signed_at=_parse_dt(s.get("signedAt")), observation=s.get("observation"),
            )
            for s in self._load("signatures") if s["responseId"] in ids
        ]

    def get_additional_answers(self, response_ids: list[int]) -> list[AdditionalAnswerRow]:
        ids = set(response_ids)
        return [
            AdditionalAnswerRow(
                response_id=a["responseId"], additional_question_id=a["additionalQuestionId"],
                question=a.get("question"), question_text=a.get("questionText"),
                answer_boolean=a.get("answerBoolean"),
            )
            for a in self._load("additional_answers") if a["responseId"] in ids
        ]

    def get_observation_options(self, response_ids: list[int]) -> list[ObservationOptionRow]:
        ids = set(response_ids)
        return [
            ObservationOptionRow(
                response_id=o["responseId"], question_id=o.get("questionId"),
                list_title=o.get("listTitle"), options=o.get("options"),
            )
            for o in self._load("observation_options") if o["responseId"] in ids
        ]

    def get_tickets(self, response_ids: list[int]) -> list[TicketRow]:
        ids = set(response_ids)
        return [
            TicketRow(
                response_id=t["responseId"], ticket_id=t["ticketId"],
                form_instance_id=t.get("formInstanceId"), title=t.get("title"),
                state=t.get("state"), priority=t.get("priority"), created_at=_parse_dt(t.get("createdAt")),
            )
            for t in self._load("tickets") if t["responseId"] in ids
        ]

    def resolve_asset(self, path: str) -> SourceAsset:
        asset_path = self._dir / "assets" / Path(path).name
        if not asset_path.exists():
            return SourceAsset(path=path, found=False)
        content_type, _ = mimetypes.guess_type(str(asset_path))
        return SourceAsset(
            path=path, found=True, content=asset_path.read_bytes(),
            content_type=content_type or "application/octet-stream",
        )
