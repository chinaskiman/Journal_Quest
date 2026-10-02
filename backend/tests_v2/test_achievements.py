"""Achievements: verifiable unlocks, immutability, hidden visibility."""
from __future__ import annotations

from tests_v2.conftest import make_trade, seed_settings


def _ach(client):
    return {a["code"]: a for a in client.get("/api/achievements").json()["items"]}


def test_first_trade_unlock(client):
    seed_settings(client)
    make_trade(client)
    ach = _ach(client)
    assert ach["ACH-INIT-TRADE"]["unlocked"] is True
    assert ach["ACH-INIT-QR"]["unlocked"] is False


def test_unlock_idempotent_and_immutable(client):
    seed_settings(client)
    make_trade(client)
    _ach(client)   # evaluate twice
    ach = _ach(client)
    unlocked_at = ach["ACH-INIT-TRADE"]["unlocked_at"]
    assert unlocked_at is not None
    _ach(client)  # third evaluation - no duplicates, timestamp unchanged
    ach = _ach(client)
    assert ach["ACH-INIT-TRADE"]["unlocked_at"] == unlocked_at


def test_hidden_achievements_stay_hidden_until_unlocked(client):
    seed_settings(client)
    ach = _ach(client)
    secret = ach["ACH-SECRET-NIGHT"]
    assert secret["unlocked"] is False
    assert secret["name"] == "???"          # masked
    assert secret["description"] == "Hidden achievement."

    make_trade(client, opened_at="2026-10-01T02:30:00")  # night shift
    ach = _ach(client)
    secret = ach["ACH-SECRET-NIGHT"]
    assert secret["unlocked"] is True
    assert secret["name"] == "Night Shift"  # revealed


def test_phoenix_requires_complete_deep_review_on_manual_loss(client):
    seed_settings(client)
    trade = make_trade(client, status="closed", result="loss")
    client.post(f"/api/trades/{trade['id']}/deep-review", json={
        "plan_review": "a", "execution_review": "b",
    })
    assert _ach(client)["ACH-SECRET-PHOENIX"]["unlocked"] is False  # incomplete
    dr = client.get(f"/api/trades/{trade['id']}/deep-review").json()
    client.patch(f"/api/deep-reviews/{dr['id']}", json={
        "risk_review": "c", "emotions_review": "d", "mistakes": "e",
    })
    assert _ach(client)["ACH-SECRET-PHOENIX"]["unlocked"] is True


def test_no_pnl_or_risk_based_conditions():
    from app2.services.achievements import ACHIEVEMENT_CATALOG
    forbidden = ("pnl", "profit", "win rate", "risk", "volume", "lot")
    for a in ACHIEVEMENT_CATALOG:
        blob = (a.name + a.description).lower()
        for word in forbidden:
            assert word not in blob, f"{a.code} mentions {word}"


def test_seen_marker_only_mutable_field(client):
    seed_settings(client)
    make_trade(client)
    client.get("/api/achievements")  # ensure evaluated
    assert client.post("/api/achievements/ACH-INIT-TRADE/seen").status_code == 204
    assert client.post("/api/achievements/ACH-INIT-QR/seen").status_code == 404
