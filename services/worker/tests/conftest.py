from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.config import Settings
from app.source.fixture_repository import FixtureSourceRepository
from app.source.models import ReportFilters

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def repo(fixtures_dir: Path) -> FixtureSourceRepository:
    return FixtureSourceRepository(fixtures_dir)


@pytest.fixture
def settings(tmp_path: Path, fixtures_dir: Path) -> Settings:
    return Settings(
        SOURCE_ADAPTER="fixture",
        FIXTURES_DIR=str(fixtures_dir),
        STORAGE_BACKEND="local",
        LOCAL_STORAGE_DIR=str(tmp_path / "output"),
        EMAIL_BACKEND="console",
    )


@pytest.fixture
def july_filters() -> ReportFilters:
    return ReportFilters(
        company_id=254, form_id=100,
        date_from=datetime(2026, 7, 1), date_to_exclusive=datetime(2026, 8, 1),
        evaluation_point_ids=[], include_all_points=True,
    )
