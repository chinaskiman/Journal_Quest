"""xp_awarded / level_up response feedback for frontend integration.

Every XP-earning mutation must report the XP the ledger actually recorded
for that operation and a level_up payload ONLY when that mutation crossed
a level threshold.  Edits never award and never report a level-up.
"""
from __future__ import annotations

from tests_v2.conftest import make_trade, seed_settings, xp_total


def test_trade_create_reports_xp_awarded_and_no_level_up(client):
    seed_settings(client)
    body = make_trade(client)
    assert body["xp_awarded"] == 20
    assert body["level_up"] is None
    assert xp_total(client) == 20


def test_trade_create_reports_real_level_up_at_boundary(client):
    """Level 2 is reached at exactly 100 XP: the 5th trade (+20) triggers it."""
    seed_settings(client)
    for i in range(4):
        body = make_trade(client)
        assert body["level_up"] is None
    body = make_trade(client)
    assert xp_total(client) == 100
    assert body["xp_awarded"] == 20
    assert body["level_up"] == {"level": 2, "title": "Signal Listener"}


def test_quick_review_reports_xp(client):
    seed_settings(client)
    t = make_trade(client)
    r = client.post(f"/api/trades/{t['id']}/quick-review",
                    json={"execution_rating": 4})
    assert r.status_code == 201
    assert r.json()["xp_awarded"] == 15
    assert r.json()["level_up"] is None
    assert xp_total(client) == 35


def test_deep_review_includes_capped_lesson_xp(client):
    seed_settings(client)
    t = make_trade(client)
    r = client.post(f"/api/trades/{t['id']}/deep-review", json={
        "mistakes": "m", "lessons": [
            {"text": "one"}, {"text": "two"}, {"text": "three"},
            {"text": "four"},  # beyond the 3-per-review cap -> no XP
        ],
    })
    assert r.status_code == 201
    body = r.json()
    assert body["xp_awarded"] == 60  # 30 deep + 3 x 10 lessons
    assert body["level_up"] is None
    assert xp_total(client) == 80


def test_standalone_lesson_reports_capped_xp(client):
    """A standalone lesson tied to a parent review reports its awarded XP;
    further lessons beyond the 3-per-review cap report 0 (saved, no XP)."""
    seed_settings(client)
    t = make_trade(client)
    qr = client.post(f"/api/trades/{t['id']}/quick-review",
                     json={"execution_rating": 3}).json()
    r = client.post("/api/lessons", json={
        "source_type": "quick", "source_id": qr["id"], "text": "l1"})
    assert r.json()["xp_awarded"] == 10
    # a lesson with no parent review id never earns XP (existing rule)
    r = client.post("/api/lessons", json={"source_type": "daily", "text": "l2"})
    assert r.json()["xp_awarded"] == 0


def test_emotional_entry_reports_first_and_additional(client):
    seed_settings(client)
    r1 = client.post("/api/emotional-entries", json={
        "emotion": "Calm", "intensity": 3, "occurred_at": "2026-10-01T10:00:00",
    })
    assert r1.json()["xp_awarded"] == 10
    r2 = client.post("/api/emotional-entries", json={
        "emotion": "Anxious", "intensity": 4, "occurred_at": "2026-10-01T16:00:00",
    })
    assert r2.json()["xp_awarded"] == 2  # additional entry same local day
    assert xp_total(client) == 12


def test_daily_and_weekly_review_report_xp(client):
    seed_settings(client)
    r = client.post("/api/daily-reviews/2026-10-01", json={"energy": 3})
    assert r.json()["xp_awarded"] == 15
    r = client.post("/api/weekly-reviews/2026-W40", json={})
    assert r.json()["xp_awarded"] == 30


def test_claim_reports_awarded_xp_and_level_up(client):
    seed_settings(client)
    make_trade(client)          # +20 (FT-01 completes)
    make_trade(client)          # +20
    # push total to 80 so the +25 claim crosses the 100 XP level-2 boundary
    client.post("/api/emotional-entries", json={
        "emotion": "Calm", "intensity": 3, "occurred_at": "2026-10-01T10:00:00",
    })  # +10
    r = client.post("/api/trades/1/quick-review", json={"execution_rating": 3})
    assert r.status_code == 201  # +15 -> total 65
    r = client.post("/api/trades/2/quick-review", json={"execution_rating": 3})
    assert r.status_code == 201  # +15 -> total 80
    r = client.post("/api/quests/FT-01/claim")
    assert r.status_code == 200
    body = r.json()
    assert body["awarded_xp"] == 25
    assert body["level_up"] == {"level": 2, "title": "Signal Listener"}
    assert xp_total(client) == 105


def test_edits_report_nothing_and_award_nothing(client):
    """PATCH responses are unchanged (no xp_awarded key) and award 0 XP."""
    seed_settings(client)
    t = make_trade(client)
    r = client.patch(f"/api/trades/{t['id']}", json={"notes": "x"})
    assert r.status_code == 200
    assert "xp_awarded" not in r.json()
    assert xp_total(client) == 20
