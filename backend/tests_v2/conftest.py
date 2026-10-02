"""Shared fixtures for the Trade Quest v2 test suite.

The environment is pointed at a throw-away v2 database *before* any app2
module is imported, so tests never touch real data - and use a distinct env
var (TRADEQUEST2_DB) from the v1 suite so both suites stay independent.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_TMP = tempfile.mkdtemp(prefix="tradequest_v2_tests_")
os.environ["TRADEQUEST2_DB"] = os.path.join(_TMP, "test_v2.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app2.db import Base, SessionLocal, engine  # noqa: E402


def _clean_tables():
    for table in reversed(Base.metadata.sorted_tables):
        with engine.begin() as conn:
            conn.execute(table.delete())


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
    _clean_tables()


@pytest.fixture()
def client():
    from app2.main import app

    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    _clean_tables()


def seed_settings(client: TestClient) -> dict:
    """Minimal settings lists so categorical validation can pass."""
    out = {}
    client.post("/api/settings/symbols", json={"name": "EURUSD"})
    client.post("/api/settings/symbols", json={"name": "XAUUSD"})
    client.post("/api/settings/setups", json={"name": "Breakout"})
    client.post("/api/settings/emotions", json={"name": "Calm"})
    client.post("/api/settings/emotions", json={"name": "Anxious"})
    out["symbol"], out["setup"], out["emotion"] = "EURUSD", "Breakout", "Calm"
    return out


def make_trade(client: TestClient, **overrides) -> dict:
    payload = {"symbol": "EURUSD", "opened_at": "2026-10-01T09:30:00"}
    payload.update(overrides)
    resp = client.post("/api/trades", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def xp_events(client: TestClient) -> list[dict]:
    return client.get("/api/xp/events", params={"page_size": 500}).json()["rows"]


def xp_total(client: TestClient) -> int:
    return client.get("/api/xp").json()["total_xp"]
