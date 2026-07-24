"""Construye ReportData (modelo de dominio) a partir de las filas de la fuente.

Clave del MVP: NO multiplicar preguntas por fotografías, firmas, tickets ni
preguntas adicionales. Cada consulta llega por separado y se agrupa aquí.
"""
from __future__ import annotations

from ..source.models import (
    AdditionalAnswerRow,
    ObservationOptionRow,
    QuestionAnswerRow,
    ResponseHeader,
    ResponseImageRow,
    ResponseSignatureRow,
    TicketRow,
)
from .model import (
    AdditionalAnswer,
    AuditableEntity,
    AuditorData,
    CompanyData,
    EvaluationPoint,
    FormData,
    ReportData,
    ReportImage,
    ReportQuestion,
    ReportSection,
    SignatureData,
    TicketData,
)
from .compliance import evaluate
from .observation_options import parse_observation_options


def _duration(started, completed) -> str | None:
    if started is None or completed is None:
        return None
    try:
        total = int((completed - started).total_seconds())
    except (TypeError, ValueError):
        return None
    if total < 0:
        return None
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _group_by_response(rows: list) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for row in rows:
        grouped.setdefault(row.response_id, []).append(row)
    return grouped


def build_report_data(
    header: ResponseHeader,
    questions: list[QuestionAnswerRow],
    images: list[ResponseImageRow],
    signatures: list[ResponseSignatureRow],
    additional: list[AdditionalAnswerRow],
    observation_options: list[ObservationOptionRow],
    tickets: list[TicketRow],
) -> ReportData:
    """Construye el informe de UNA respuesta a partir de sus filas ya filtradas."""
    warnings: list[str] = []

    # Imágenes agrupadas por pregunta (solo source_path; el binario se resuelve luego).
    images_by_question: dict[int | None, list[ReportImage]] = {}
    for img in images:
        images_by_question.setdefault(img.question_id, []).append(ReportImage(source_path=img.path))

    # Opciones de observación agrupadas por pregunta.
    options_by_question: dict[int | None, list[str]] = {}
    for opt in observation_options:
        options_by_question.setdefault(opt.question_id, []).extend(parse_observation_options(opt.options))

    # Tickets que apuntan a una pregunta específica no vienen en TicketRow (solo por respuesta);
    # se muestran a nivel de informe. Se agregan a la pregunta solo si `creates_ticket`.
    report_tickets = [
        TicketData(ticket_id=t.ticket_id, title=t.title, state=t.state, priority=t.priority, created_at=t.created_at)
        # Ordenar por fecha como texto ISO para evitar comparar datetimes naive/aware.
        for t in sorted(tickets, key=lambda x: (x.created_at.isoformat() if x.created_at else "", x.ticket_id))
    ]

    # Agrupar preguntas por ítem manteniendo orden determinista.
    # Orden de sección = primera aparición (mínimo `order` observado; si es None, orden de llegada).
    section_order: dict[str, int] = {}
    section_weight: dict[str, float | None] = {}
    section_questions: dict[str, list[ReportQuestion]] = {}
    for idx, q in enumerate(questions):
        item_name = q.item_name or "Sin ítem"
        if item_name not in section_order:
            # Orden de sección = orden de aparición en el resultado de la fuente
            # (la consulta llega ordenada por ítem/orden). No se asume que la
            # ponderación del ítem represente el orden. Ver docs/notas.
            section_order[item_name] = idx
            section_weight[item_name] = q.item_weight
            section_questions[item_name] = []
        comp_label, comp_value = evaluate(q.answer, q.answer_type)
        report_q = ReportQuestion(
            question_id=q.question_id,
            response_question_id=q.response_question_id,
            order=q.order,
            statement=q.statement,
            question_type=q.question_type,
            answer=q.answer,
            compliance_label=comp_label,
            compliance_value=comp_value,
            score=q.score,
            max_points=q.question_weight,
            observation=q.observation,
            tooltip=q.tooltip,
            requires_photo=q.requires_photo,
            requires_observation=q.requires_observation,
            creates_ticket=q.creates_ticket,
            observation_options=options_by_question.get(q.question_id, []),
            images=images_by_question.get(q.question_id, []),
            tickets=[],
        )
        section_questions[item_name].append(report_q)

    sections: list[ReportSection] = []
    for ordinal, name in enumerate(sorted(section_order, key=lambda n: (section_order[n], n)), start=1):
        qs = sorted(
            section_questions[name],
            key=lambda q: (q.order if q.order is not None else 1_000_000, q.question_id),
        )
        # Numeración ítem.posición (p. ej. "1.5") por posición dentro del ítem.
        for pos, q in enumerate(qs, start=1):
            q.number = f"{ordinal}.{pos}"
        # Cumplimiento del ítem = puntos obtenidos / puntos máximos de sus preguntas
        # (rp.ponderacion / p.ponderacion), igual que el informe oficial de ToCheck.
        # Nota obtenida = ponderación del ítem × cumplimiento.
        weight = section_weight[name]
        sum_max = sum(q.max_points for q in qs if q.max_points is not None)
        sum_ach = sum(q.score for q in qs if q.max_points is not None and q.score is not None)
        if sum_max > 0:
            pct = sum_ach / sum_max * 100
        else:
            # Sin ponderaciones por pregunta (p. ej. fixtures): promedio de cumplimiento.
            values = [q.compliance_value for q in qs if q.compliance_value is not None]
            pct = (sum(values) / len(values) * 100) if values else None
        obtained = (weight * pct / 100) if (weight is not None and pct is not None) else None
        sections.append(ReportSection(
            name=name, ordinal=ordinal, weight=weight,
            obtained=obtained, compliance_pct=pct, questions=qs,
        ))

    if not sections:
        warnings.append("La respuesta no contiene preguntas.")

    evaluation_point = None
    if header.evaluation_point_id is not None or header.evaluation_point_name:
        evaluation_point = EvaluationPoint(
            id=header.evaluation_point_id, name=header.evaluation_point_name,
            address=header.evaluation_point_address, country=header.evaluation_point_country,
            zone=header.zone_name,
        )
    auditable_entity = None
    if header.auditable_entity_id is not None or header.auditable_entity_name:
        auditable_entity = AuditableEntity(
            id=header.auditable_entity_id, name=header.auditable_entity_name,
            identifier_code=header.auditable_entity_code, email=header.auditable_entity_email,
            entity_type=header.auditable_entity_type,
        )
    auditor = None
    if header.user_name or header.user_last_name or header.user_position:
        auditor = AuditorData(
            name=header.user_name, last_name=header.user_last_name, position=header.user_position
        )

    return ReportData(
        response_id=header.response_id,
        company=CompanyData(id=header.company_id, name=header.company_name, logo=header.company_logo),
        form=FormData(
            id=header.form_id, name=header.form_name, code=header.form_code,
            scale=header.form_scale, logo=header.form_logo,
        ),
        evaluation_point=evaluation_point,
        auditable_entity=auditable_entity,
        auditor=auditor,
        completed_at=header.completed_at,
        started_at=header.started_at,
        duration=_duration(header.started_at, header.completed_at),
        score=header.score,
        scale=header.form_scale,
        general_observation=header.general_observation,
        coordinates=header.coordinates,
        timing=header.timing,
        sections=sections,
        additional_answers=[
            AdditionalAnswer(question=a.question, question_text=a.question_text, answer=a.answer_boolean)
            for a in additional
        ],
        signatures=[
            SignatureData(
                signer_name=s.signer_name, signer_last_name=s.signer_last_name,
                signer_email=s.signer_email, signer_position=s.signer_position, status=s.status,
                sent_at=s.sent_at, signed_at=s.signed_at, observation=s.observation,
            )
            for s in signatures
        ],
        tickets=report_tickets,
        warnings=warnings,
    )
