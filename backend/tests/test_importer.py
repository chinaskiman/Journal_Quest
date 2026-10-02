"""Importer tests - run against the real workbook (skipped if missing)."""
from __future__ import annotations

import pytest

from conftest import REAL_WORKBOOK

from app.importer import import_workbook
from app.models import OptionValue, Trade
from app.serializers import serialize_trades

pytestmark = pytest.mark.skipif(
    not REAL_WORKBOOK.exists(), reason="source workbook not available"
)


@pytest.fixture()
def imported(db_session):
    report = import_workbook(REAL_WORKBOOK, db_session, mode="replace")
    return db_session, report


def test_import_counts(imported):
    db, report = imported
    assert report.trades_imported == 11  # includes the 2 open AUDUSD rows
    assert db.query(Trade).count() == 11
    assert report.options_imported > 0


def test_verbatim_values_preserved(imported):
    db, _ = imported
    types = {
        v for (v,) in db.query(OptionValue.value).filter_by(list_key="setup_type")
    }
    assert "welcome" in types  # non-standard value kept verbatim
    symbols = {
        v for (v,) in db.query(OptionValue.value).filter_by(list_key="symbol")
    }
    assert "XCUUSD" in symbols  # the typo'd symbol is NOT normalized


def test_row_order_and_seq(imported):
    db, _ = imported
    seqs = [s for (s,) in db.query(Trade.seq).order_by(Trade.seq)]
    assert seqs == list(range(1, 12))


def test_derived_matches_workbook_statuses(imported):
    db, _ = imported
    rows = serialize_trades(db.query(Trade).order_by(Trade.seq).all())
    statuses = [r["status"] for r in rows]
    assert statuses == ["Win", "Win", "Win", "Loss", "Loss", "Loss", "Loss",
                        "Win", "Loss", "Open", "Open"]


def test_open_trades_have_no_pnl(imported):
    db, _ = imported
    rows = serialize_trades(db.query(Trade).order_by(Trade.seq).all())
    for row in rows[9:]:
        assert row["closing_price"] is None
        assert row["net_pnl"] is None
        assert row["final_rr"] is None
        assert row["duration_seconds"] is None


def test_source_net_pnl_audit_column(imported):
    db, _ = imported
    rows = serialize_trades(db.query(Trade).order_by(Trade.seq).all())
    assert rows[0]["source_net_pnl"] == 161.94  # literal workbook value
    assert abs(rows[0]["net_pnl"] - 161.12224299065275) < 1e-9  # live math


def test_analytics_matches_workbook_cached_figures(imported):
    from app.analytics import build_analytics

    db, _ = imported
    rows = serialize_trades(db.query(Trade).order_by(Trade.seq).all())
    lists: dict[str, list[str]] = {}
    for key, value in db.query(OptionValue.list_key, OptionValue.value).order_by(
        OptionValue.position
    ):
        lists.setdefault(key, []).append(value)
    payload = build_analytics(rows, lists)

    assert payload["overview"]["total_trades"] == 11
    assert payload["overview"]["closed_trades"] == 9
    assert payload["overview"]["open_trades"] == 2
    assert payload["overview"]["wins"] == 4
    assert payload["overview"]["losses"] == 5
    assert abs(payload["overview"]["win_rate"] - 4 / 9) < 1e-9
    # cached workbook values: avg realized R 1.2332, avg risk 33.2836
    assert abs(payload["risk"]["average_realized_r"] - 1.2331782665117954) < 1e-9
    assert abs(payload["risk"]["average_risk"] - 33.28363636363636) < 1e-9
    assert payload["risk"]["max_consecutive_wins"] == 3
    assert payload["risk"]["max_consecutive_losses"] == 4


def test_reimport_replace_is_idempotent(imported):
    db, _ = imported
    import_workbook(REAL_WORKBOOK, db, mode="replace")
    assert db.query(Trade).count() == 11
