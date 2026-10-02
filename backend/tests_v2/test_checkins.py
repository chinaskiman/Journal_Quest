"""Daily Review (+15/date) and Weekly Review (+30/ISO week) XP rules."""
from __future__ import annotations

from tests_v2.conftest import seed_settings, xp_total


def test_daily_review_plus15_once(client):
    seed_settings(client)
    r = client.post("/api/daily-reviews/2026-10-01",
                    json={"energy": 4, "focus": 3, "mood": 4,
                          "reflection": "steady day"})
    assert r.status_code == 201
    assert xp_total(client) == 15
    # duplicate for same date -> 409, no double XP
    assert client.post("/api/daily-reviews/2026-10-01", json={}).status_code == 409
    assert xp_total(client) == 15
    # edit -> no re-award
    client.patch("/api/daily-reviews/2026-10-01", json={"energy": 2})
    assert xp_total(client) == 15
    # another date -> another +15
    assert client.post("/api/daily-reviews/2026-10-02", json={}).status_code == 201
    assert xp_total(client) == 30


def test_daily_review_invalid_date_rejected(client):
    seed_settings(client)
    assert client.post("/api/daily-reviews/2026-13-01", json={}).status_code == 422


def test_weekly_review_plus30_once(client):
    seed_settings(client)
    r = client.post("/api/weekly-reviews/2026-W40",
                    json={"highlights": "good", "challenges": "patience",
                          "patterns": "overtrading after wins",
                          "plan_next_week": "fewer, better trades"})
    assert r.status_code == 201
    body = r.json()
    assert body["iso_year"] == 2026 and body["iso_week"] == 40
    assert xp_total(client) == 30
    # duplicate same ISO week -> 409
    assert client.post("/api/weekly-reviews/2026-W40", json={}).status_code == 409
    assert xp_total(client) == 30
    # edit -> no re-award
    client.patch("/api/weekly-reviews/2026-W40", json={"highlights": "z"})
    assert xp_total(client) == 30
    # next ISO week -> another +30
    assert client.post("/api/weekly-reviews/2026-W41", json={}).status_code == 201
    assert xp_total(client) == 60


def test_weekly_review_key_is_iso_year_week(client):
    from app2.db import SessionLocal
    from app2.models import XpEvent
    seed_settings(client)
    client.post("/api/weekly-reviews/2026-W01", json={})
    client.post("/api/daily-reviews/2026-01-01", json={})
    with SessionLocal() as db:
        keys = {row.idempotency_key: row.amount
                for row in db.query(XpEvent).all()}
    assert keys.get("weekly:2026-01") == 30
    assert keys.get("daily:2026-01-01") == 15


def test_weekly_review_bad_format(client):
    seed_settings(client)
    assert client.post("/api/weekly-reviews/2026-40", json={}).status_code == 422
    assert client.post("/api/weekly-reviews/2026-W99", json={}).status_code == 422
