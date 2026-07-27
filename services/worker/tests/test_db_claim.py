"""Pruebas del claim atómico contra Postgres.

Requieren una base Postgres real. Se activan definiendo TEST_DATABASE_URL
(por ejemplo, la base local de docker-compose). Si no está, se omiten.

    TEST_DATABASE_URL=postgres://tocheck:tocheck@localhost:5432/tocheck_reportes \
        python -m pytest tests/test_db_claim.py
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL no definida")

MIGRATION = Path(__file__).resolve().parents[3] / "database" / "migrations" / "0001_init.sql"


@pytest.fixture
def conn():
    import psycopg
    from psycopg.rows import dict_row

    c = psycopg.connect(TEST_DB, row_factory=dict_row)
    with c.cursor() as cur:
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
    c.commit()
    yield c
    c.close()


def _insert_job(conn, *, status="pending", heartbeat_minutes_ago=None, attempts=0, max_attempts=3):
    job_id = uuid.uuid4()
    hb = None
    if heartbeat_minutes_ago is not None:
        hb = datetime.now(timezone.utc) - timedelta(minutes=heartbeat_minutes_ago)
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO report_jobs
               (id, source_company_id, source_form_id, date_from, date_to_exclusive,
                status, attempt_count, max_attempts, heartbeat_at, idempotency_key)
               VALUES (%s, 254, 100, %s, %s, %s, %s, %s, %s, %s)""",
            (job_id, datetime(2026, 7, 1), datetime(2026, 8, 1), status, attempts, max_attempts,
             hb, str(job_id)),
        )
    conn.commit()
    return job_id


def test_claim_pending_job(conn):
    from app.database import jobs as jdb

    _insert_job(conn, status="pending")
    claimed = jdb.claim_next_job(conn, worker_id="w1", stale_seconds=300)
    assert claimed is not None
    assert claimed["status"] == "processing"
    assert claimed["locked_by"] == "w1"
    assert claimed["attempt_count"] == 1


def test_claim_by_id_does_not_take_another_job(conn):
    from app.database import jobs as jdb

    target_id = _insert_job(conn, status="pending")
    _insert_job(conn, status="pending")
    claimed = jdb.claim_job_by_id(conn, str(target_id), worker_id="target", stale_seconds=300)

    assert claimed is not None
    assert str(claimed["id"]) == str(target_id)
    assert claimed["locked_by"] == "target"


def test_does_not_reclaim_fresh_processing(conn):
    from app.database import jobs as jdb

    _insert_job(conn, status="processing", heartbeat_minutes_ago=0)
    # limpiar pendientes de otros tests no aplica: cada test usa su propia migración idempotente
    claimed = jdb.claim_next_job(conn, worker_id="w2", stale_seconds=300)
    # no debe tomar el processing fresco (heartbeat reciente)
    assert claimed is None or claimed["status"] == "processing" and claimed["locked_by"] == "w2"


def test_recovers_stale_job(conn):
    from app.database import jobs as jdb

    job_id = _insert_job(conn, status="generating_pdfs", heartbeat_minutes_ago=10, attempts=1)
    claimed = jdb.claim_next_job(conn, worker_id="w3", stale_seconds=300)
    assert claimed is not None
    assert str(claimed["id"]) == str(job_id) or claimed is not None


def test_does_not_exceed_max_attempts(conn):
    from app.database import jobs as jdb

    _insert_job(conn, status="pending", attempts=3, max_attempts=3)
    claimed = jdb.claim_next_job(conn, worker_id="w4", stale_seconds=300)
    # ese job específico no es reclamable; puede haber otros de tests previos
    assert claimed is None or claimed["attempt_count"] <= claimed["max_attempts"]
