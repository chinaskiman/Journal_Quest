"""Dashboard, settings API, XP read endpoints, validation and security."""
from __future__ import annotations

import pytest

from tests_v2.conftest import make_trade, seed_settings, xp_total


def test_dashboard_empty_state_is_honest_zeros(client):
    body = client.get("/api/dashboard").json()
    assert body["pilot"]["total_xp"] == 0
    assert body["pilot"]["level"] == 1
    assert body["quests"]["completed_count"] == 0
    assert body["quests"]["claimable_count"] == 0
    assert body["journal"]["trades_total"] == 0
    assert body["journal"]["daily_review_done_today"] is False
    assert body["recent_activity"] == []


def test_dashboard_reflects_persisted_activity(client):
    seed_settings(client)
    make_trade(client)
    body = client.get("/api/dashboard").json()
    assert body["pilot"]["total_xp"] == 20
    assert body["journal"]["trades_total"] == 1
    assert body["journal"]["open_trades"] == 1
    assert len(body["recent_activity"]) == 1
    assert body["recent_activity"][0]["event_type"] == "trade_create"


def test_dashboard_unreviewed_closed_trades(client):
    seed_settings(client)
    t = make_trade(client)
    make_trade(client)
    client.post(f"/api/trades/{t['id']}/close", json={"result": "win"})
    client.post(f"/api/trades/{t['id']}/quick-review",
                json={"execution_rating": 4})
    body = client.get("/api/dashboard").json()
    assert body["journal"]["closed_trades"] == 1
    assert body["journal"]["unreviewed_trade_ids"] == []  # the closed one is reviewed


def test_dashboard_manual_pnl_summary_echo_only(client):
    seed_settings(client)
    make_trade(client, user_pnl=100.0)
    make_trade(client, user_pnl=-30.0)
    make_trade(client)
    body = client.get("/api/dashboard").json()
    assert body["manual_pnl_summary"] == {"entries": 2, "sum": 70.0}
    # P&L echo never feeds progression
    assert body["pilot"]["total_xp"] == 60  # 3 creations only


def test_dashboard_pilot_contract_at_a_mid_level_total(client):
    """The pilot block must expose the full, self-consistent level payload.

    The UI reads these fields verbatim, so the API contract is pinned here at a
    state that is *inside* a level (not on a threshold): 6 trades = 120 XP ->
    level 2 (base 100), 20 XP earned in the level, 130 XP still needed.
    """
    seed_settings(client)
    for _ in range(6):
        make_trade(client)

    pilot = client.get("/api/dashboard").json()["pilot"]
    summary = client.get("/api/xp").json()

    # One derivation, two endpoints - they must never drift apart.
    assert pilot == summary
    assert pilot["total_xp"] == 120
    assert pilot["level"] == 2
    assert pilot["title"] == "Signal Listener"
    assert pilot["current_level_xp"] == 20
    # next_level_xp_needed is what is LEFT (not the 150-XP level span)
    assert pilot["next_level_xp_needed"] == 130
    assert pilot["next_level_total_xp"] == 250
    assert pilot["current_level_xp"] + pilot["next_level_xp_needed"] == 150
    assert pilot["progress_pct"] == pytest.approx(20 / 150 * 100, abs=0.01)


def test_dashboard_pilot_empty_state_fields_are_complete(client):
    """A fresh database still returns every pilot field the UI renders."""
    pilot = client.get("/api/dashboard").json()["pilot"]
    assert pilot["total_xp"] == 0
    assert pilot["level"] == 1
    assert pilot["current_level_xp"] == 0
    assert pilot["next_level_xp_needed"] == 100
    assert pilot["next_level_total_xp"] == 100
    assert pilot["progress_pct"] == 0


def test_settings_crud(client):
    r = client.post("/api/settings/symbols", json={"name": "EURUSD"})
    assert r.status_code == 201
    assert r.json()["is_active"] is True
    assert client.post("/api/settings/symbols",
                       json={"name": "EURUSD"}).status_code == 409
    assert client.get("/api/settings/nope").status_code == 404

    sid = r.json()["id"]
    r = client.patch(f"/api/settings/symbols/{sid}", json={"name": "EUR"})
    assert r.json()["name"] == "EUR"
    assert client.delete(f"/api/settings/symbols/{sid}").status_code == 204
    assert client.get("/api/settings/symbols").json()["items"] == []


def test_empty_setting_name_rejected(client):
    assert client.post("/api/settings/symbols",
                       json={"name": "   "}).status_code == 422


def test_preferences_roundtrip(client):
    assert client.get("/api/preferences").json()["items"] == {}
    r = client.put("/api/preferences/theme", json={"value": '"nebula"'})
    assert r.status_code == 200
    assert client.get("/api/preferences").json()["items"]["theme"] == "nebula"
    assert client.put("/api/preferences/bad",
                      json={"value": "not json"}).status_code == 422


def test_no_xp_injection_through_extra_fields(client):
    seed_settings(client)
    resp = client.post("/api/trades", json={
        "symbol": "EURUSD", "opened_at": "2026-10-01T09:00",
        "xp": 999999, "amount": 999999,
    })
    assert resp.status_code == 422  # extra="forbid" rejects unknown fields
    assert xp_total(client) == 0


def test_xp_events_read_only(client):
    seed_settings(client)
    make_trade(client)
    events = client.get("/api/xp/events").json()
    assert events["total"] == 1
    assert events["rows"][0]["amount"] == 20


def test_levels_endpoint_exposes_approved_thresholds(client):
    body = client.get("/api/levels").json()
    thresholds = {t["level"]: t["cumulative_xp"] for t in body["thresholds"]}
    assert thresholds[2] == 100 and thresholds[10] == 2700


def test_validation_error_structure(client):
    resp = client.post("/api/trades", json={"opened_at": "2026-10-01T09:00"})
    assert resp.status_code == 422  # symbol required
    assert "detail" in resp.json()


def test_backup_and_health(client):
    assert client.get("/api/system/health").json()["host"] == "127.0.0.1"
    r = client.get("/api/system/backup")
    assert r.status_code == 200
    assert r.json()["backup"].startswith("tradequest_v2_")
    assert len(client.get("/api/system/backups").json()["items"]) >= 1
