from __future__ import annotations

from datetime import datetime

from app.source.models import ReportFilters


def test_list_companies(repo):
    companies = repo.list_companies()
    assert any(c.id == 254 and c.name == "Tarragona Retail" for c in companies)


def test_list_forms_only_with_responses(repo):
    forms = repo.list_forms(254)
    ids = {f.id for f in forms}
    assert 100 in ids and 101 in ids


def test_count_all_points(repo, july_filters):
    count = repo.count_responses(july_filters)
    # Form 100 tiene 3 respuestas en julio (128483, 128485, 128490).
    assert count.total_responses == 3
    assert count.total_evaluation_points == 3


def test_count_subset_of_points(repo):
    filters = ReportFilters(
        company_id=254, form_id=100,
        date_from=datetime(2026, 7, 1), date_to_exclusive=datetime(2026, 8, 1),
        evaluation_point_ids=[900], include_all_points=False,
    )
    count = repo.count_responses(filters)
    assert count.total_responses == 1  # solo Providencia (128483)


def test_count_empty_result(repo):
    filters = ReportFilters(
        company_id=254, form_id=100,
        date_from=datetime(2026, 1, 1), date_to_exclusive=datetime(2026, 2, 1),
        evaluation_point_ids=[], include_all_points=True,
    )
    assert repo.count_responses(filters).total_responses == 0


def test_date_upper_bound_is_exclusive(repo):
    # 128490 se completó 2026-07-20T16:45. Un límite exclusivo en ese instante lo excluye.
    filters = ReportFilters(
        company_id=254, form_id=100,
        date_from=datetime(2026, 7, 20), date_to_exclusive=datetime(2026, 7, 20, 16, 45),
        evaluation_point_ids=[], include_all_points=True,
    )
    ids = repo.list_response_ids(filters)
    assert 128490 not in ids


def test_list_response_ids_ordered(repo, july_filters):
    ids = repo.list_response_ids(july_filters)
    assert ids == [128483, 128485, 128490]
