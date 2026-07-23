"""Modelos crudos de la fuente (una capa fina sobre las filas SQL).

Estos modelos NO son el modelo de dominio del PDF; son lo que devuelve el
SourceRepository. El builder los transforma en ReportData.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _SourceModel(BaseModel):
    # La fuente (MySQL de ToCheck) devuelve enteros donde a veces esperamos texto
    # (p. ej. `estado` de firma = 0/1). Coercionar números a str evita romper el job
    # ante sorpresas de tipos en datos reales.
    model_config = ConfigDict(coerce_numbers_to_str=True)


class ReportFilters(BaseModel):
    company_id: int
    form_id: int
    date_from: datetime
    date_to_exclusive: datetime
    evaluation_point_ids: list[int] = []
    include_all_points: bool = True


class SourceCompany(_SourceModel):
    id: int
    name: str
    logo: str | None = None


class SourceForm(_SourceModel):
    id: int
    company_id: int
    name: str
    code: str | None = None
    scale: str | None = None
    logo: str | None = None
    welcome_message: str | None = None


class SourceEvaluationPoint(_SourceModel):
    id: int | None
    name: str | None = None
    address: str | None = None
    country: str | None = None
    zone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ResponseCount(BaseModel):
    total_responses: int
    total_evaluation_points: int


class ResponseHeader(_SourceModel):
    response_id: int
    company_id: int
    company_name: str | None = None
    company_logo: str | None = None
    form_id: int
    form_name: str | None = None
    form_code: str | None = None
    form_scale: str | None = None
    form_logo: str | None = None
    evaluation_point_id: int | None = None
    evaluation_point_name: str | None = None
    evaluation_point_address: str | None = None
    evaluation_point_country: str | None = None
    zone_name: str | None = None
    auditable_entity_id: int | None = None
    auditable_entity_name: str | None = None
    auditable_entity_code: str | None = None
    auditable_entity_email: str | None = None
    auditable_entity_type: str | None = None
    user_id: int | None = None
    user_name: str | None = None
    user_last_name: str | None = None
    user_position: str | None = None
    # Nota: RUT y correo personal NO se persisten ni se muestran (minimización).
    completed_at: datetime
    started_at: datetime | None = None
    score: float | None = None
    general_observation: str | None = None
    coordinates: str | None = None
    timing: str | None = None


class QuestionAnswerRow(_SourceModel):
    response_id: int
    response_question_id: int
    question_id: int
    item_id: int | None = None
    item_name: str | None = None
    item_weight: float | None = None
    order: int | None = None
    statement: str
    question_type: str | None = None
    answer: str | None = None
    score: float | None = None
    observation: str | None = None
    tooltip: str | None = None
    requires_photo: bool | None = None
    requires_observation: bool | None = None
    creates_ticket: bool | None = None


class ResponseImageRow(_SourceModel):
    response_id: int
    question_id: int | None = None
    path: str


class ResponseSignatureRow(_SourceModel):
    response_id: int
    signer_user_id: int | None = None
    signer_name: str | None = None
    signer_last_name: str | None = None
    status: str | None = None
    sent_at: datetime | None = None
    signed_at: datetime | None = None
    observation: str | None = None


class AdditionalAnswerRow(_SourceModel):
    response_id: int
    additional_question_id: int
    question: str | None = None
    question_text: str | None = None
    answer_boolean: bool | None = None


class ObservationOptionRow(_SourceModel):
    response_id: int
    question_id: int | None = None
    list_title: str | None = None
    options: str | None = None  # texto | JSON | separado por comas


class TicketRow(_SourceModel):
    response_id: int
    ticket_id: int
    form_instance_id: int | None = None
    title: str | None = None
    state: str | None = None
    priority: int | None = None
    created_at: datetime | None = None


class SourceAsset(BaseModel):
    path: str
    found: bool
    content: bytes | None = None
    content_type: str | None = None

    model_config = {"arbitrary_types_allowed": True}
