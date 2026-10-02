"""Trade CRUD, manual close, manual P&L, screenshot handling, zero-XP rules."""
from __future__ import annotations

import pytest

from tests_v2.conftest import make_trade, seed_settings, xp_events, xp_total


def setup_module(module):
    pass  # each test uses its own client fixture


def test_trade_crud_roundtrip(client):
    seed_settings(client)
    trade = make_trade(
        client, setup="Breakout", direction="long",
        entry_price=1.085, screenshot_path=r"C:\shots\chart.png",
        thesis="Higher timeframe bullish", notes="textbook entry",
    )
    tid = trade["id"]
    assert trade["status"] == "open"
    assert trade["symbol_label"] == "EURUSD"
    assert trade["entry_price"] == 1.085
    assert trade["screenshot_path"] == r"C:\shots\chart.png"  # stored as text only

    # read + list
    assert client.get(f"/api/trades/{tid}").json()["id"] == tid
    assert client.get("/api/trades").json()["total"] == 1

    # update
    resp = client.patch(f"/api/trades/{tid}", json={"notes": "updated"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "updated"

    # delete (soft) hides from default list
    client.delete(f"/api/trades/{tid}")
    assert client.get("/api/trades").json()["total"] == 0
    assert client.get("/api/trades",
                      params={"include_deleted": True}).json()["total"] == 1


def test_trade_create_awards_20_xp(client):
    seed_settings(client)
    make_trade(client)
    events = xp_events(client)
    assert [e["amount"] for e in events] == [20]
    assert events[0]["idempotency_key"].startswith("capture:")
    assert xp_total(client) == 20


def test_manual_close_awards_zero_xp(client):
    seed_settings(client)
    trade = make_trade(client)
    resp = client.post(f"/api/trades/{trade['id']}/close", json={
        "exit_price": 1.09, "result": "win", "user_pnl": 120.5,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "closed"
    assert body["result"] == "win"
    assert body["user_pnl"] == 120.5
    assert xp_total(client) == 20  # only creation XP; close adds ZERO

    # closing again -> 409, still no extra XP
    assert client.post(f"/api/trades/{trade['id']}/close", json={}).status_code == 409
    assert xp_total(client) == 20


def test_manual_pnl_variants_and_no_xp(client):
    seed_settings(client)
    t1 = make_trade(client, user_pnl=150.25)      # positive
    t2 = make_trade(client, user_pnl=-80.0)       # negative
    t3 = make_trade(client, user_pnl=0)           # zero
    t4 = make_trade(client)                       # null
    assert t1["user_pnl"] == 150.25
    assert t2["user_pnl"] == -80.0
    assert t3["user_pnl"] == 0
    assert t4["user_pnl"] is None
    # update P&L
    resp = client.patch(f"/api/trades/{t4['id']}", json={"user_pnl": -12.5})
    assert resp.json()["user_pnl"] == -12.5
    # 4 creations only - P&L entry/edit never awards XP
    assert xp_total(client) == 80


def test_trade_edit_and_delete_award_no_xp(client):
    seed_settings(client)
    trade = make_trade(client)
    client.patch(f"/api/trades/{trade['id']}", json={"notes": "x", "user_pnl": 5})
    client.delete(f"/api/trades/{trade['id']}")
    assert xp_total(client) == 20


def test_pnl_never_computed_from_prices(client):
    seed_settings(client)
    trade = make_trade(client, entry_price=100.0, direction="long")
    client.post(f"/api/trades/{trade['id']}/close", json={"exit_price": 110.0})
    body = client.get(f"/api/trades/{trade['id']}").json()
    assert body["entry_price"] == 100.0
    assert body["exit_price"] == 110.0
    assert body["user_pnl"] is None  # never inferred


def test_direction_validation(client):
    seed_settings(client)
    resp = client.post("/api/trades", json={
        "symbol": "EURUSD", "opened_at": "2026-10-01T09:00",
        "direction": "sideways",
    })
    assert resp.status_code == 422


def test_screenshot_endpoint_safety(client, tmp_path, monkeypatch):
    allowed = tmp_path / "shots"
    allowed.mkdir()
    monkeypatch.setenv("TRADEQUEST2_SCREENSHOT_DIRS", str(allowed))
    seed_settings(client)
    img = allowed / "chart.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    trade = make_trade(client, screenshot_path=str(img))
    resp = client.get(f"/api/trades/{trade['id']}/screenshot")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image")

    # non-image extension refused
    secret = allowed / "secrets.txt"
    secret.write_text("secret")
    t2 = make_trade(client, screenshot_path=str(secret))
    assert client.get(f"/api/trades/{t2['id']}/screenshot").status_code == 422

    # missing file inside the allowed dir -> 404, not an error leak
    t3 = make_trade(client, screenshot_path=str(allowed / "does_not_exist.png"))
    assert client.get(f"/api/trades/{t3['id']}/screenshot").status_code == 404


def test_screenshot_fails_closed_when_unconfigured(client, tmp_path, monkeypatch):
    monkeypatch.delenv("TRADEQUEST2_SCREENSHOT_DIRS", raising=False)
    seed_settings(client)
    img = tmp_path / "chart.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    trade = make_trade(client, screenshot_path=str(img))
    r = client.get(f"/api/trades/{trade['id']}/screenshot")
    assert r.status_code == 422
    assert "TRADEQUEST2_SCREENSHOT_DIRS" in r.json()["detail"]


def test_screenshot_outside_permitted_dirs_rejected(client, tmp_path, monkeypatch):
    allowed = tmp_path / "shots"
    allowed.mkdir()
    monkeypatch.setenv("TRADEQUEST2_SCREENSHOT_DIRS", str(allowed))
    seed_settings(client)
    outside = tmp_path / "elsewhere" / "chart.png"
    outside.parent.mkdir()
    outside.write_bytes(b"\x89PNG\r\n\x1a\n")
    trade = make_trade(client, screenshot_path=str(outside))
    r = client.get(f"/api/trades/{trade['id']}/screenshot")
    assert r.status_code == 422
    assert "outside" in r.json()["detail"]


def test_screenshot_traversal_rejected(client, tmp_path, monkeypatch):
    allowed = tmp_path / "shots"
    (allowed / "sub").mkdir(parents=True)
    monkeypatch.setenv("TRADEQUEST2_SCREENSHOT_DIRS", str(allowed))
    seed_settings(client)
    secret = tmp_path / "wallet.txt.png"  # image extension, wrong directory
    secret.write_bytes(b"\x89PNG\r\n\x1a\n")
    escape = str(allowed / "sub" / ".." / ".." / "wallet.txt.png")
    trade = make_trade(client, screenshot_path=escape)
    assert client.get(f"/api/trades/{trade['id']}/screenshot").status_code == 422


def test_screenshot_junction_escape_rejected(client, tmp_path, monkeypatch):
    """A junction inside the allowed dir pointing outside must be refused."""
    import subprocess

    allowed = tmp_path / "shots"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    junction = allowed / "link"
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        pytest.skip(f"junction creation not permitted on this host: {proc.stderr}")
    monkeypatch.setenv("TRADEQUEST2_SCREENSHOT_DIRS", str(allowed))
    seed_settings(client)
    trade = make_trade(client, screenshot_path=str(junction / "chart.png"))
    assert client.get(f"/api/trades/{trade['id']}/screenshot").status_code == 422


def test_screenshot_oversize_rejected(client, tmp_path, monkeypatch):
    allowed = tmp_path / "shots"
    allowed.mkdir()
    monkeypatch.setenv("TRADEQUEST2_SCREENSHOT_DIRS", str(allowed))
    seed_settings(client)
    big = allowed / "huge.png"
    big.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * (25 * 1024 * 1024 + 1))
    trade = make_trade(client, screenshot_path=str(big))
    assert client.get(f"/api/trades/{trade['id']}/screenshot").status_code == 422


def test_screenshot_case_insensitive_root_match(client, tmp_path, monkeypatch):
    """Windows paths are case-insensitive - an upper-case root must match."""
    allowed = tmp_path / "Shots"
    allowed.mkdir()
    monkeypatch.setenv("TRADEQUEST2_SCREENSHOT_DIRS", str(allowed).upper())
    seed_settings(client)
    img = allowed / "chart.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    trade = make_trade(client, screenshot_path=str(img))
    assert client.get(f"/api/trades/{trade['id']}/screenshot").status_code == 200
