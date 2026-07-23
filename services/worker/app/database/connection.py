"""Conexión a la base operativa (Neon)."""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row


def connect(database_url: str) -> psycopg.Connection:
    conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=False)
    return conn
