"""Database foundation tests: fresh init, empty state, constraints,
persistence across restart, rollback, historical label preservation."""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from app2.db import Base, SessionLocal, engine, initialize_db
from app2.models import DailyReview, Symbol, Trade, XpEvent


def test_fresh_database_is_created_and_empty(client):
    tables = set(Base.metadata.tables)
    assert {"trades", "quick_reviews", "deep_reviews", "lessons",
            "emotional_entries", "daily_reviews", "weekly_reviews",
            "xp_events", "quest_progress", "achievement_unlocks",
            "ui_preferences", "app_meta", "symbols", "setups",
            "emotions"} <= tables
    with SessionLocal() as db:
        for model in (Trade, XpEvent, DailyReview, Symbol):
            assert db.query(model).count() == 0, f"{model.__tablename__} not empty"


def test_initialize_db_is_idempotent_and_never_drops_data(client):
    with SessionLocal() as db:
        db.add(Trade(symbol_label="X", opened_at=dt.datetime(2026, 1, 1, 9)))
        db.commit()
    initialize_db()  # repeat init must not drop anything
    with SessionLocal() as db:
        assert db.query(Trade).count() == 1


def test_persistence_across_restart(client):
    from tests_v2.conftest import make_trade, seed_settings

    seed_settings(client)
    make_trade(client)
    total_before = client.get("/api/xp").json()["total_xp"]
    # simulate restart: brand-new session against the same engine/file
    initialize_db()
    with SessionLocal() as db:
        assert db.query(Trade).count() == 1
        assert db.query(XpEvent).count() == 1
    assert client.get("/api/xp").json()["total_xp"] == total_before


def test_xp_idempotency_key_unique_constraint(db_session):
    db_session.add(XpEvent(event_type="trade_create", amount=20,
                           idempotency_key="capture:1"))
    db_session.flush()
    db_session.add(XpEvent(event_type="trade_create", amount=20,
                           idempotency_key="capture:1"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_daily_review_date_unique(db_session):
    db_session.add(DailyReview(review_date=dt.date(2026, 10, 1)))
    db_session.flush()
    db_session.add(DailyReview(review_date=dt.date(2026, 10, 1)))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_trade_result_check_constraint(db_session):
    db_session.add(Trade(symbol_label="X", opened_at=dt.datetime(2026, 1, 1),
                         result="huge_win"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_transaction_rollback_leaves_nothing_partial(client):
    """A failed XP-awarding operation must not leave partial commits."""
    from tests_v2.conftest import seed_settings, xp_events

    seed_settings(client)
    before = xp_events(client)
    # symbol not in settings -> 422 -> nothing persisted, no XP
    resp = client.post("/api/trades", json={
        "symbol": "NOPE", "opened_at": "2026-10-01T09:00:00"})
    assert resp.status_code == 422
    assert client.get("/api/trades").json()["total"] == 0
    assert len(xp_events(client)) == len(before)


def test_historical_label_preserved_after_rename_and_soft_delete(client):
    from tests_v2.conftest import make_trade, seed_settings

    seed_settings(client)
    trade = make_trade(client, setup="Breakout")
    # rename the setup
    sid = client.get("/api/settings/setups").json()["items"][0]["id"]
    client.patch(f"/api/settings/setups/{sid}", json={"name": "Breakout v2"})
    # history keeps the snapshot
    got = client.get(f"/api/trades/{trade['id']}").json()
    assert got["setup_label"] == "Breakout"

    # create a trade referencing the renamed label, then soft delete symbol
    trade2 = make_trade(client, setup="Breakout v2")
    client.delete(f"/api/settings/setups/{sid}")  # soft delete
    items = client.get("/api/settings/setups").json()["items"]
    assert items == []  # hidden from active list
    all_items = client.get("/api/settings/setups",
                           params={"include_inactive": True}).json()["items"]
    assert len(all_items) == 1  # but still archived and distinguishable
    # trades keep their historical labels
    assert client.get(f"/api/trades/{trade2['id']}").json()["setup_label"] == "Breakout v2"

    # hard delete is refused while referenced
    resp = client.delete(f"/api/settings/setups/{sid}", params={"hard": True})
    assert resp.status_code == 409
