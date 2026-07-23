from __future__ import annotations

import copy

from app.reports.builder import build_report_data
from app.reports.hashing import cache_key, source_payload_hash
from app.reports.images import resolve_report_images


def _build(repo, response_id):
    header = {h.response_id: h for h in repo.get_response_headers([response_id])}[response_id]
    return build_report_data(
        header, repo.get_response_questions([response_id]), repo.get_response_images([response_id]),
        repo.get_response_signatures([response_id]), repo.get_additional_answers([response_id]),
        repo.get_observation_options([response_id]), repo.get_tickets([response_id]),
    )


def test_hash_is_deterministic(repo):
    a = _build(repo, 128483)
    b = _build(repo, 128483)
    assert source_payload_hash(a) == source_payload_hash(b)


def test_hash_changes_with_visible_data(repo):
    a = _build(repo, 128483)
    b = _build(repo, 128483)
    b.sections[0].questions[0].answer = "CAMBIADO"
    assert source_payload_hash(a) != source_payload_hash(b)


def test_hash_ignores_warnings(repo):
    a = _build(repo, 128483)
    b = copy.deepcopy(a)
    b.warnings.append("un aviso cualquiera")
    assert source_payload_hash(a) == source_payload_hash(b)


def test_cache_key_includes_versions():
    k1 = cache_key(1, "hash", "1", "1")
    k2 = cache_key(1, "hash", "2", "1")
    assert k1 != k2


def test_failed_image_produces_warning_and_placeholder(repo):
    data = _build(repo, 128485)  # referencia a missing-broken-image.jpg
    resolve_report_images(data, repo)
    images = [img for s in data.sections for q in s.questions for img in q.images]
    assert any(img.failed and img.data_uri is None for img in images)
    assert any("missing-broken-image" in w for w in data.warnings)


def test_valid_images_get_data_uri(repo):
    data = _build(repo, 128483)
    resolve_report_images(data, repo)
    images = [img for s in data.sections for q in s.questions for img in q.images]
    ok = [img for img in images if not img.failed]
    assert len(ok) == 2
    assert all(img.data_uri and img.data_uri.startswith("data:image/jpeg;base64,") for img in ok)
