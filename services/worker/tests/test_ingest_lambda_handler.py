"""Tests del handler Lambda de ingest."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import ingest_lambda_handler


def test_handler_runs_ingest_for_company(monkeypatch):
    settings = SimpleNamespace(source_company_id=254)
    monkeypatch.setattr(ingest_lambda_handler, "get_settings", lambda: settings)
    monkeypatch.setattr(
        ingest_lambda_handler,
        "get_last_synced_upper_bound",
        lambda s, c: None,
    )
    monkeypatch.setattr(
        ingest_lambda_handler,
        "resolve_ingest_window",
        lambda **kwargs: (datetime(2026, 7, 1), datetime(2026, 7, 28)),
    )
    called = {}

    def fake_ingest(settings, *, company_id, date_from, date_to_exclusive):
        called.update(
            company_id=company_id,
            date_from=date_from,
            date_to_exclusive=date_to_exclusive,
        )
        return {"responses_upserted": 3}

    monkeypatch.setattr(ingest_lambda_handler, "ingest_snapshot", fake_ingest)

    result = ingest_lambda_handler.handler(
        {"schemaVersion": 1, "companyId": 254, "lookbackDays": 7},
        SimpleNamespace(aws_request_id="req-1"),
    )
    assert result["schemaVersion"] == 1
    assert result["companies"][0]["companyId"] == 254
    assert result["companies"][0]["responses_upserted"] == 3
    assert called["company_id"] == 254


def test_handler_requires_company(monkeypatch):
    monkeypatch.setattr(
        ingest_lambda_handler,
        "get_settings",
        lambda: SimpleNamespace(source_company_id=None),
    )
    with pytest.raises(ValueError, match="companyId"):
        ingest_lambda_handler.handler({}, MagicMock())


def test_handler_parses_company_ids_list(monkeypatch):
    settings = SimpleNamespace(source_company_id=None)
    monkeypatch.setattr(ingest_lambda_handler, "get_settings", lambda: settings)
    monkeypatch.setattr(ingest_lambda_handler, "get_last_synced_upper_bound", lambda s, c: None)
    monkeypatch.setattr(
        ingest_lambda_handler,
        "resolve_ingest_window",
        lambda **kwargs: (datetime(2026, 7, 1), datetime(2026, 7, 2)),
    )
    seen: list[int] = []

    def fake_ingest(settings, *, company_id, date_from, date_to_exclusive):
        seen.append(company_id)
        return {"responses_upserted": 0}

    monkeypatch.setattr(ingest_lambda_handler, "ingest_snapshot", fake_ingest)
    ingest_lambda_handler.handler(
        {"schemaVersion": 1, "companyIds": [10, 20]},
        SimpleNamespace(aws_request_id="x"),
    )
    assert seen == [10, 20]


def test_handler_explicit_date_from_skips_last_sync(monkeypatch):
    settings = SimpleNamespace(source_company_id=3)
    monkeypatch.setattr(ingest_lambda_handler, "get_settings", lambda: settings)
    called_last = {"n": 0}

    def fake_last(settings, company_id):
        called_last["n"] += 1
        return datetime(2026, 7, 21)

    monkeypatch.setattr(ingest_lambda_handler, "get_last_synced_upper_bound", fake_last)

    captured = {}

    def fake_window(**kwargs):
        captured.update(kwargs)
        return (kwargs["date_from"], kwargs["date_to_exclusive"] or datetime(2026, 7, 29))

    monkeypatch.setattr(ingest_lambda_handler, "resolve_ingest_window", fake_window)
    monkeypatch.setattr(
        ingest_lambda_handler,
        "ingest_snapshot",
        lambda settings, **kw: {"responses_upserted": 1},
    )

    ingest_lambda_handler.handler(
        {
            "schemaVersion": 1,
            "companyIds": "3",
            "dateFrom": "2026-05-01T00:00:00",
            "dateToExclusive": "2026-07-29T00:00:00",
        },
        SimpleNamespace(aws_request_id="x"),
    )
    assert called_last["n"] == 0
    assert captured["date_from"] == datetime(2026, 5, 1)
    assert captured["last_synced_upper_bound"] is None
