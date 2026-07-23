"""Modelo de dominio normalizado del informe. La plantilla Jinja2 SOLO recibe esto.

Es independiente del SQL: no hay duplicación de filas por fotos/firmas/tickets.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CompanyData(BaseModel):
    id: int
    name: str | None = None
    logo: str | None = None


class FormData(BaseModel):
    id: int
    name: str | None = None
    code: str | None = None
    scale: str | None = None
    logo: str | None = None


class EvaluationPoint(BaseModel):
    id: int | None = None
    name: str | None = None
    address: str | None = None
    country: str | None = None
    zone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class AuditableEntity(BaseModel):
    id: int | None = None
    name: str | None = None
    identifier_code: str | None = None
    email: str | None = None
    entity_type: str | None = None


class AuditorData(BaseModel):
    name: str | None = None
    last_name: str | None = None
    position: str | None = None


class ReportImage(BaseModel):
    # Ruta original en la fuente (clave lógica); el dato binario resuelto va aparte.
    source_path: str
    # data URI listo para la plantilla (o None si falló y se usa placeholder).
    data_uri: str | None = None
    failed: bool = False


class TicketData(BaseModel):
    ticket_id: int
    title: str | None = None
    state: str | None = None
    priority: int | None = None
    created_at: datetime | None = None


class ReportQuestion(BaseModel):
    question_id: int
    response_question_id: int
    order: int | None = None
    statement: str
    question_type: str | None = None
    answer: str | bool | int | float | list | None = None
    score: float | None = None
    observation: str | None = None
    tooltip: str | None = None
    requires_photo: bool | None = None
    requires_observation: bool | None = None
    creates_ticket: bool | None = None
    observation_options: list[str] = []
    images: list[ReportImage] = []
    tickets: list[TicketData] = []


class ReportSection(BaseModel):
    name: str
    weight: float | None = None
    questions: list[ReportQuestion] = []


class AdditionalAnswer(BaseModel):
    question: str | None = None
    question_text: str | None = None
    answer: bool | None = None


class SignatureData(BaseModel):
    signer_name: str | None = None
    signer_last_name: str | None = None
    status: str | None = None
    sent_at: datetime | None = None
    signed_at: datetime | None = None
    observation: str | None = None
    # Punto de extensión: cuando se identifique el campo de imagen de firma dibujada,
    # agregar aquí `signature_image_data_uri: str | None`.


class ReportData(BaseModel):
    response_id: int
    company: CompanyData
    form: FormData
    evaluation_point: EvaluationPoint | None = None
    auditable_entity: AuditableEntity | None = None
    auditor: AuditorData | None = None
    completed_at: datetime
    started_at: datetime | None = None
    score: float | None = None
    scale: str | None = None
    general_observation: str | None = None
    coordinates: str | None = None  # no se muestra por defecto (dato sensible)
    timing: str | None = None
    sections: list[ReportSection] = []
    additional_answers: list[AdditionalAnswer] = []
    signatures: list[SignatureData] = []
    tickets: list[TicketData] = []
    warnings: list[str] = []
