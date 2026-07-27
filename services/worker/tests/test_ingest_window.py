"""Ingesta incremental: la ventana debe basarse en fecha+hora, no solo el día."""
from __future__ import annotations

from datetime import datetime

from app.source.ingest import resolve_ingest_window

NOW = datetime(2026, 7, 24, 15, 30, 0)


def test_explicit_date_from_overrides_last_sync():
    # Un backfill manual siempre gana, aunque exista una corrida previa.
    start, end = resolve_ingest_window(
        date_from=datetime(2026, 7, 1, 0, 0, 0), date_to_exclusive=None,
        last_synced_upper_bound=datetime(2026, 7, 20, 9, 0, 0),
        lookback_days=7, now=NOW,
    )
    assert start == datetime(2026, 7, 1, 0, 0, 0)
    assert end == NOW


def test_continues_from_exact_last_sync_timestamp():
    # No debe "redondear" al día: sigue exactamente desde la hora:minuto:segundo previos.
    last = datetime(2026, 7, 21, 14, 22, 37)
    start, end = resolve_ingest_window(
        date_from=None, date_to_exclusive=None,
        last_synced_upper_bound=last, lookback_days=7, now=NOW,
    )
    assert start == last
    assert start.hour == 14 and start.minute == 22 and start.second == 37
    assert end == NOW


def test_falls_back_to_lookback_when_no_prior_sync():
    start, end = resolve_ingest_window(
        date_from=None, date_to_exclusive=None,
        last_synced_upper_bound=None, lookback_days=7, now=NOW,
    )
    assert start == datetime(2026, 7, 17, 0, 0, 0)  # NOW - 7 días, a medianoche
    assert end == NOW


def test_explicit_end_overrides_now():
    start, end = resolve_ingest_window(
        date_from=None, date_to_exclusive=datetime(2026, 7, 22, 0, 0, 0),
        last_synced_upper_bound=datetime(2026, 7, 20, 9, 0, 0),
        lookback_days=7, now=NOW,
    )
    assert end == datetime(2026, 7, 22, 0, 0, 0)


def test_end_defaults_to_now_not_next_day():
    # Antes el fin por defecto era "mañana a medianoche"; ahora es el instante actual,
    # para que la siguiente corrida pueda continuar sin reprocesar horas ya cubiertas.
    _, end = resolve_ingest_window(
        date_from=datetime(2026, 7, 1), date_to_exclusive=None,
        last_synced_upper_bound=None, lookback_days=7, now=NOW,
    )
    assert end == NOW
