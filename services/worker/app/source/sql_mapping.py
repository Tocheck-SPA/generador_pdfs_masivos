"""Mapeo de filas SQL (alias en snake_case) a los modelos de la fuente.

Compartido por los adaptadores PostgreSQL y MySQL: ambas consultas usan los
mismos alias de columna, por lo que el mapeo es idéntico.
"""
from __future__ import annotations

from .models import (
    AdditionalAnswerRow,
    ObservationOptionRow,
    QuestionAnswerRow,
    ResponseHeader,
    ResponseImageRow,
    ResponseSignatureRow,
    SourceCompany,
    SourceEvaluationPoint,
    SourceForm,
    TicketRow,
)


def as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_bool(value) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("1", "true", "t", "si", "sí", "yes")


def map_company(r: dict) -> SourceCompany:
    return SourceCompany(id=r["id_empresa"], name=r["nombre_empresa"], logo=r.get("logo_empresa"))


def map_form(r: dict, company_id: int) -> SourceForm:
    return SourceForm(
        id=r["id_formulario"], company_id=company_id, name=r["nombre_formulario"],
        code=r.get("codigo_formulario"), scale=r.get("escala_formulario"), logo=r.get("logo_formulario"),
    )


def map_point(r: dict) -> SourceEvaluationPoint:
    return SourceEvaluationPoint(
        id=r["id_punto_evaluacion"], name=r.get("nombre_punto"), address=r.get("direccion_punto"),
        country=r.get("pais_punto"), zone=r.get("nombre_zona"),
    )


def map_header(r: dict) -> ResponseHeader:
    return ResponseHeader(
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
        score=as_float(r.get("ponderacion_total")), general_observation=r.get("observacion_general"),
        coordinates=r.get("coordenada"),
        timing=(str(r["timing"]) if r.get("timing") is not None else None),
    )


def map_question(r: dict) -> QuestionAnswerRow:
    return QuestionAnswerRow(
        response_id=r["id_respuesta"], response_question_id=r["id_respuesta_pregunta"],
        question_id=r["id_pregunta"], item_id=r.get("id_item"), item_name=r.get("nombre_item"),
        item_weight=as_float(r.get("ponderacion_item")), order=r.get("orden_pregunta"),
        statement=r.get("enunciado_pregunta") or "", question_type=r.get("tipo_pregunta"),
        answer_type=r.get("tipo_resp"),
        answer=(str(r["valor_respuesta"]) if r.get("valor_respuesta") is not None else None),
        score=as_float(r.get("ponderacion_respuesta")),
        question_weight=as_float(r.get("ponderacion_pregunta")),
        observation=r.get("observacion_respuesta"), tooltip=r.get("tooltip_pregunta"),
        requires_photo=to_bool(r.get("requiere_foto_pregunta")),
        requires_observation=to_bool(r.get("requiere_observacion_pregunta")),
        creates_ticket=to_bool(r.get("genera_ticket")),
    )


def map_image(r: dict) -> ResponseImageRow:
    return ResponseImageRow(response_id=r["id_respuesta"], question_id=r.get("id_pregunta"), path=r["path"])


def map_signature(r: dict) -> ResponseSignatureRow:
    return ResponseSignatureRow(
        response_id=r["id_respuesta"], signer_user_id=r.get("id_usuario_firmador"),
        signer_name=r.get("nombre_firmador"), signer_last_name=r.get("apellido_firmador"),
        signer_email=r.get("email_firmador"), signer_position=r.get("cargo_firmador"),
        status=r.get("estado_firma"), sent_at=r.get("fecha_envio_firma"),
        signed_at=r.get("fecha_firma"), observation=r.get("observacion_firma"),
    )


def map_additional(r: dict) -> AdditionalAnswerRow:
    return AdditionalAnswerRow(
        response_id=r["id_respuesta"], additional_question_id=r["id_pregunta_adicional"],
        question=r.get("pregunta"), question_text=r.get("pregunta_texto"),
        answer_boolean=to_bool(r.get("respuesta_adicional_boolean")),
    )


def map_option(r: dict) -> ObservationOptionRow:
    return ObservationOptionRow(
        response_id=r["id_respuesta"], question_id=r.get("id_pregunta"),
        list_title=r.get("titulo_lista"),
        options=(str(r["opciones"]) if r.get("opciones") is not None else None),
    )


def map_ticket(r: dict) -> TicketRow:
    return TicketRow(
        response_id=r["id_respuesta"], ticket_id=r["id_ticket"],
        form_instance_id=r.get("id_formulario_instancia"), title=r.get("titulo_ticket"),
        state=r.get("ticket_estado"), priority=r.get("prioridad"), created_at=r.get("created_at"),
    )
