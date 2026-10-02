"""Shared fixtures.

Environment is pointed at a throw-away database *before* any app module is
imported, so every test session runs fully isolated from real data.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMP = tempfile.mkdtemp(prefix="tradequest_tests_")
os.environ["TRADEQUEST_DB"] = os.path.join(_TMP, "test.db")
os.environ["TRADEQUEST_EXCEL"] = os.path.join(_TMP, "missing.xlsx")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402

REAL_WORKBOOK = PROJECT_ROOT / "Trading Journla-Reaction Based Strategy.xlsx"


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
    from app.main import app

    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    _clean_tables()


def _clean_tables():
    for table in reversed(Base.metadata.sorted_tables):
        with engine.begin() as conn:
            conn.execute(table.delete())


def seed_options(session) -> None:
    """Minimal option lists so categorical validation can pass."""
    from app.models import OptionValue

    seeds = {
        "symbol": ["EURUSD", "XAUUSD"],
        "setup_type": ["Breakout", "Rejection"],
        "bias": ["Bullish", "Bearish", "Neutral"],
        "rsi_condition": ["Rising from Support", "Exiting Oversold"],
        "mental_state": ["Calm", "Confident"],
    }
    for key, values in seeds.items():
        for position, value in enumerate(values, start=1):
            session.add(OptionValue(list_key=key, value=value, position=position))
    session.commit()
