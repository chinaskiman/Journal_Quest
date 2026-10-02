"""Quick Review, Deep Review and Lesson XP rules."""
from __future__ import annotations

from tests_v2.conftest import make_trade, seed_settings, xp_events, xp_total


def _qr(client, trade_id, **over):
    payload = {"execution_rating": 4}
    payload.update(over)
    return client.post(f"/api/trades/{trade_id}/quick-review", json=payload)


def _dr(client, trade_id, lessons=(), **over):
    payload = {"plan_review": "ok", "execution_review": "good",
               "risk_review": "tight", "emotions_review": "calm",
               "mistakes": "chased once", "grade": "B",
               "key_takeaway": "wait for confirmation",
               "lessons": [{"text": t} for t in lessons]}
    payload.update(over)
    return client.post(f"/api/trades/{trade_id}/deep-review", json=payload)


def test_quick_review_plus15_once(client):
    seed_settings(client)
    trade = make_trade(client)
    assert _qr(client, trade["id"]).status_code == 201
    assert xp_total(client) == 20 + 15
    # duplicate creation refused; edit does not re-award
    assert _qr(client, trade["id"]).status_code == 409
    r = client.get(f"/api/trades/{trade['id']}/quick-review").json()
    client.patch(f"/api/quick-reviews/{r['id']}",
                 json={"execution_rating": 2, "improve": "be patient"})
    assert xp_total(client) == 35


def test_deep_review_plus30_once(client):
    seed_settings(client)
    trade = make_trade(client)
    assert _dr(client, trade["id"]).status_code == 201
    assert xp_total(client) == 20 + 30
    assert _dr(client, trade["id"]).status_code == 409
    dr = client.get(f"/api/trades/{trade['id']}/deep-review").json()
    client.patch(f"/api/deep-reviews/{dr['id']}", json={"grade": "A"})
    assert xp_total(client) == 50


def test_lesson_xp_capped_at_3_per_deep_review(client):
    seed_settings(client)
    trade = make_trade(client)
    r = _dr(client, trade["id"], lessons=["l1", "l2", "l3", "l4", "l5"])
    assert r.status_code == 201
    body = r.json()
    assert len(body["lessons"]) == 5  # all saved
    lesson_events = [e for e in xp_events(client) if e["event_type"] == "lesson"]
    assert len(lesson_events) == 3  # only first 3 earn XP
    assert xp_total(client) == 20 + 30 + 30


def test_lessons_beyond_cap_added_later_earn_nothing(client):
    seed_settings(client)
    trade = make_trade(client)
    _dr(client, trade["id"], lessons=["a", "b", "c"])
    dr = client.get(f"/api/trades/{trade['id']}/deep-review").json()
    # add two more lessons via the standalone endpoint
    for text in ("d", "e"):
        r = client.post("/api/lessons", json={
            "source_type": "deep", "source_id": dr["id"], "text": text})
        assert r.status_code == 201
    lessons = client.get("/api/lessons", params={"source_type": "deep"}).json()
    assert lessons["total"] == 5  # stored
    lesson_events = [e for e in xp_events(client) if e["event_type"] == "lesson"]
    assert len(lesson_events) == 3  # cap not exceeded


def test_lesson_retry_cannot_double_earn(client):
    """Each lesson id has its own immutable ledger key."""
    seed_settings(client)
    trade = make_trade(client)
    _dr(client, trade["id"], lessons=["only"])
    lid = client.get("/api/lessons").json()["rows"][0]["id"]
    client.patch(f"/api/lessons/{lid}", json={"text": "edited lesson"})
    lesson_events = [e for e in xp_events(client) if e["event_type"] == "lesson"]
    assert len(lesson_events) == 1


def test_delete_review_no_clawback(client):
    seed_settings(client)
    trade = make_trade(client)
    _qr(client, trade["id"])
    r = client.get(f"/api/trades/{trade['id']}/quick-review").json()
    client.delete(f"/api/quick-reviews/{r['id']}")
    assert xp_total(client) == 35  # 20 + 15, unchanged


def test_lesson_xp_independent_of_another_review(client):
    """A second deep review gets its own 3-lesson budget."""
    seed_settings(client)
    t1, t2 = make_trade(client), make_trade(client)
    _dr(client, t1["id"], lessons=["a", "b", "c", "d"])
    _dr(client, t2["id"], lessons=["e"])
    lesson_events = [e for e in xp_events(client) if e["event_type"] == "lesson"]
    assert len(lesson_events) == 4  # 3 from review 1 + 1 from review 2


def test_rating_validation(client):
    seed_settings(client)
    trade = make_trade(client)
    assert _qr(client, trade["id"], execution_rating=9).status_code == 422
