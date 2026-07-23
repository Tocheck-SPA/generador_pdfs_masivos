from __future__ import annotations


def _build(repo, response_id: int):
    from app.reports.builder import build_report_data

    header = {h.response_id: h for h in repo.get_response_headers([response_id])}[response_id]
    return build_report_data(
        header,
        repo.get_response_questions([response_id]),
        repo.get_response_images([response_id]),
        repo.get_response_signatures([response_id]),
        repo.get_additional_answers([response_id]),
        repo.get_observation_options([response_id]),
        repo.get_tickets([response_id]),
    )


def test_no_question_multiplication_by_photos(repo):
    data = _build(repo, 128483)
    all_questions = [q for s in data.sections for q in s.questions]
    # 5 preguntas únicas, aunque q1001 tenga 2 fotos.
    assert len(all_questions) == 5
    q1001 = next(q for q in all_questions if q.question_id == 1001)
    assert len(q1001.images) == 2


def test_sections_group_and_order_by_appearance(repo):
    data = _build(repo, 128483)
    # Orden de aparición en la fuente: Seguridad, Limpieza, Atención al cliente.
    assert [s.name for s in data.sections] == ["Seguridad", "Limpieza", "Atención al cliente"]


def test_signatures_do_not_multiply_questions(repo):
    data = _build(repo, 128483)
    assert len(data.signatures) == 1
    all_questions = [q for s in data.sections for q in s.questions]
    assert len(all_questions) == 5


def test_additional_answers_separate(repo):
    data = _build(repo, 128483)
    assert len(data.additional_answers) == 2
    assert data.additional_answers[0].answer is True


def test_tickets_present(repo):
    data = _build(repo, 128483)
    assert len(data.tickets) == 1
    assert data.tickets[0].priority == 2


def test_observation_options_attached_to_question(repo):
    data = _build(repo, 128483)
    q1005 = next(q for s in data.sections for q in s.questions if q.question_id == 1005)
    assert q1005.observation_options == ["Ninguna"]


def test_point_only_response(repo):
    data = _build(repo, 128490)
    assert data.evaluation_point is not None
    assert data.auditable_entity is None
    assert data.score is None  # ponderación nula tolerada


def test_entity_only_response(repo):
    data = _build(repo, 128484)
    assert data.auditable_entity is not None
    assert data.auditable_entity.entity_type == "Vehículo"
    assert data.evaluation_point is None
