"""Emotional Journal XP: +10 first entry per local day, +2 after that."""
from __future__ import annotations

import datetime as dt

from tests_v2.conftest import seed_settings, xp_events, xp_total


def _entry(client, **overrides):
    payload = {"emotion": "Calm", "intensity": 3}
    payload.update(overrides)
    return client.post("/api/emotional-entries", json=payload)


def test_first_entry_of_day_plus10_second_plus2(client):
    seed_settings(client)
    r1 = _entry(client)
    assert r1.status_code == 201
    assert xp_total(client) == 10
    r2 = _entry(client)
    r3 = _entry(client, emotion="Anxious", intensity=5)
    assert xp_total(client) == 10 + 2 + 2
    types = [e["event_type"] for e in xp_events(client)]
    assert types.count("emotional_first") == 1
    assert types.count("emotional_additional") == 2


def test_additional_entries_never_get_first_bonus(client):
    seed_settings(client)
    _entry(client)
    _entry(client)
    _entry(client)
    first = [e for e in xp_events(client) if e["event_type"] == "emotional_first"]
    assert len(first) == 1


def test_new_day_gets_first_bonus_again(client):
    seed_settings(client)
    _entry(client)  # today: +10
    _entry(client)  # today: +2
    yesterday = (dt.datetime.now().astimezone() - dt.timedelta(days=1))
    r = _entry(client, occurred_at=yesterday.replace(tzinfo=None).isoformat())
    assert r.status_code == 201
    types = [e["event_type"] for e in xp_events(client)]
    assert types.count("emotional_first") == 2  # one per local day


def test_midnight_boundary_local_dates(client):
    """23:59 and 00:01 (next day) are different local calendar days."""
    seed_settings(client)
    _entry(client, occurred_at="2026-10-01T23:59:00")
    _entry(client, occurred_at="2026-10-02T00:01:00")
    types = [e["event_type"] for e in xp_events(client)]
    assert types.count("emotional_first") == 2
    assert xp_total(client) == 20


def test_client_cannot_control_day_grouping(client):
    """A UTC timestamp must be converted to the server's local date."""
    seed_settings(client)
    # 2026-10-01T23:30Z - converted server-side to local date
    r = _entry(client, occurred_at="2026-10-01T23:30:00+00:00")
    assert r.status_code == 201
    entry = r.json()
    local = dt.datetime.fromisoformat("2026-10-01T23:30:00+00:00").astimezone()
    assert entry["local_date"] == local.date().isoformat()


def test_edit_never_reawards_and_delete_never_claws_back(client):
    seed_settings(client)
    r = _entry(client)
    eid = r.json()["id"]
    client.patch(f"/api/emotional-entries/{eid}", json={"intensity": 5,
                                                        "body": "edited"})
    assert xp_total(client) == 10  # unchanged by edit
    client.delete(f"/api/emotional-entries/{eid}")
    assert xp_total(client) == 10  # no clawback after delete


def test_ledger_key_persists_across_restart(client):
    seed_settings(client)
    _entry(client)
    from app2.db import initialize_db
    from app2.models import XpEvent
    initialize_db()
    with __import__("app2.db", fromlist=["SessionLocal"]).SessionLocal() as db:
        keys = [row.idempotency_key for row in db.query(XpEvent).all()]
    assert any(k.startswith("emotional:") for k in keys)


def test_pre_existing_day_key_blocks_duplicate_first_bonus(client):
    """Simulates a concurrent race: the UNIQUE daily key is the backstop."""
    seed_settings(client)
    from app2.db import SessionLocal
    from app2.models import XpEvent
    today = dt.date.today()
    with SessionLocal() as db:
        db.add(XpEvent(event_type="emotional_first", amount=10,
                       idempotency_key=f"emotional:{today.isoformat()}"))
        db.commit()
    _entry(client)  # must see the existing key and award only +2
    assert xp_total(client) == 12


def test_link_to_trade_and_independent(client):
    seed_settings(client)
    from tests_v2.conftest import make_trade
    trade = make_trade(client)
    r = _entry(client, trade_id=trade["id"])
    assert r.status_code == 201
    assert r.json()["trade_id"] == trade["id"]
    r = _entry(client)  # independent
    assert r.json()["trade_id"] is None


def test_emotion_must_exist_in_settings(client):
    seed_settings(client)
    resp = _entry(client, emotion="Unknown")
    assert resp.status_code == 422
