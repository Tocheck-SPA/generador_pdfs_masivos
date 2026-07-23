"""El adaptador MySQL reutiliza los .sql de Postgres transformando `= ANY(...)` -> `IN ...`."""
from __future__ import annotations

from app.source.mysql_repository import _load_sql


def test_any_is_rewritten_to_in():
    sql = _load_sql("list_response_ids")
    assert "ANY(" not in sql
    assert "IN %(evaluation_point_ids)s" in sql


def test_batched_query_uses_in_for_response_ids():
    sql = _load_sql("response_headers")
    assert "ANY(" not in sql
    assert "IN %(response_ids)s" in sql
