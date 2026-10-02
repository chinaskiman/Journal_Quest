"""Quest catalog integrity, evaluation, claim workflow, consistency quests."""
from __future__ import annotations

from tests_v2.conftest import make_trade, seed_settings, xp_total


def _quests(client):
    return {q["code"]: q for q in client.get("/api/quests").json()["items"]}


def _claim(client, code):
    return client.post(f"/api/quests/{code}/claim")


def test_catalog_integrity_and_stable_codes(client):
    quests = _quests(client)
    expected = ([f"FT-0{i}" for i in range(1, 8)] +
                [f"RF-0{i}" for i in range(1, 5)] +
                [f"JM-0{i}" for i in range(1, 7)] +
                ["CN-01", "CN-02", "CN-03", "LQ-01", "LQ-02", "LQ-03"] +
                # Streak Break & Recovery (approved specification)
                ["RC-01", "RC-02"])
    assert sorted(quests) == sorted(expected)
    # standard tiers only where decided
    assert {q["reward_xp"] for q in quests.values() if q["reward_xp"]} <= {25, 50, 75, 100}


def test_quest_completion_from_persisted_activity_then_claim(client):
    seed_settings(client)
    make_trade(client)
    q = _quests(client)["FT-01"]
    assert q["progress_current"] == 1
    assert q["completed_at"] is not None
    assert q["claimed_at"] is None
    assert q["claimable"] is True
    assert xp_total(client) == 20  # completion alone awards NOTHING

    r = _claim(client, "FT-01")
    assert r.status_code == 200
    body = r.json()
    assert body["awarded_xp"] == 25
    assert body["quest"]["claimed_at"] is not None
    assert xp_total(client) == 45


def test_claim_incomplete_quest_rejected(client):
    seed_settings(client)
    assert _claim(client, "JM-04").status_code == 409
    assert xp_total(client) == 0


def test_duplicate_claim_rejected(client):
    seed_settings(client)
    make_trade(client)
    assert _claim(client, "FT-01").status_code == 200
    r = _claim(client, "FT-01")
    assert r.status_code == 409
    assert xp_total(client) == 45


def test_concurrent_claim_cannot_double_award(client):
    """Two claims in quick succession: the ledger key + claim state guard."""
    seed_settings(client)
    make_trade(client)
    r1, r2 = _claim(client, "FT-01"), _claim(client, "FT-01")
    awarded = sum(r.json().get("awarded_xp", 0) for r in (r1, r2)
                  if r.status_code == 200)
    assert awarded == 25
    assert xp_total(client) == 45


def test_claim_persists_after_restart(client):
    seed_settings(client)
    make_trade(client)
    _claim(client, "FT-01")
    from app2.db import initialize_db
    initialize_db()
    q = _quests(client)["FT-01"]
    assert q["claimed_at"] is not None
    assert q["claimable"] is False
    assert xp_total(client) == 45


def test_unknown_quest_rejected(client):
    assert _claim(client, "ZZ-99").status_code == 404


def test_client_cannot_supply_reward_amount(client):
    seed_settings(client)
    make_trade(client)
    r = client.post("/api/quests/FT-01/claim", json={"reward_xp": 100000})
    # no reward input is accepted at all - extra body simply ignored/rejected
    assert r.status_code in (200, 409)
    if r.status_code == 200:
        assert r.json()["awarded_xp"] == 25  # server-side value only


def test_consistency_quests_opt_in_and_disabled_by_default(client):
    seed_settings(client)
    for day in ("2026-10-01", "2026-10-02", "2026-10-03"):
        client.post(f"/api/daily-reviews/{day}", json={})
    quests = _quests(client)
    for code in ("CN-01", "CN-02", "CN-03"):
        assert quests[code]["opt_in"] is True
        assert quests[code]["progress_current"] == 0  # disabled -> not evaluated
        assert quests[code]["claimable"] is False
        # reward undecided -> even a completed CN quest cannot be claimed
        assert quests[code]["reward_xp"] is None


def test_consistency_rewards_undecided_but_completable_when_enabled(client):
    seed_settings(client)
    client.put("/api/preferences/consistency_quests_enabled",
               json={"value": "true"})
    for day in ("2026-10-01", "2026-10-02", "2026-10-03"):
        client.post(f"/api/daily-reviews/{day}", json={})
    quests = _quests(client)
    cn1 = quests["CN-01"]
    assert cn1["progress_current"] == 3
    assert cn1["completed_at"] is not None  # completable...
    assert cn1["claimable"] is False        # ...but NOT claimable (XP undecided)
    r = _claim(client, "CN-01")
    assert r.status_code == 409
    assert "undecided" in r.json()["detail"]


def test_consistency_reward_recorded_separately_from_entry_xp(client):
    """Quest XP and journaling XP use clearly distinct ledger event types."""
    seed_settings(client)
    make_trade(client)
    _claim(client, "FT-01")
    events = client.get("/api/xp/events").json()["rows"]
    types = {e["event_type"] for e in events}
    assert "trade_create" in types and "quest" in types


def test_deferred_quests_never_complete(client):
    """Only LQ-02 remains deferred (RF-04/LQ-03 activated by correction pass)."""
    from tests_v2.conftest import make_trade as _mk
    seed_settings(client)
    t = _mk(client)
    client.post(f"/api/trades/{t['id']}/deep-review", json={
        "mistakes": "revenge trade", "plan_review": "x",
        "execution_review": "x", "risk_review": "x", "emotions_review": "x",
    })
    quests = _quests(client)
    q = quests["LQ-02"]
    assert q["status"] == "deferred"
    assert q["completed_at"] is None
    assert _claim(client, "LQ-02").status_code == 409


def test_jm03_reward_is_exactly_75(client):
    """JM-03 'Log 50' = +75 XP is explicitly approved in the Blueprint quest
    table (JM-01..04 = 25/50/75/100).  Locked regression assertion."""
    from app2.services.quests import QUESTS_BY_CODE
    assert QUESTS_BY_CODE["JM-03"].reward_xp == 75
    assert QUESTS_BY_CODE["JM-03"].status == "active"
    assert _quests(client)["JM-03"]["reward_xp"] == 75


def _age_review(review_id: int, *, created: str, updated: str) -> None:
    """Directly set a quick review's timestamps (ORM explicit values win
    over the onupdate default, so this simulates a persisted edit)."""
    import datetime as dt

    from app2.db import SessionLocal
    from app2.models import QuickReview
    with SessionLocal() as db:
        row = db.get(QuickReview, review_id)
        row.created_at = dt.datetime.fromisoformat(created)
        row.updated_at = dt.datetime.fromisoformat(updated)
        db.commit()


def _make_quick_review(client) -> int:
    t = make_trade(client)
    r = client.post(f"/api/trades/{t['id']}/quick-review",
                    json={"execution_rating": 3})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_rf04_not_completed_before_7_days(client):
    seed_settings(client)
    rid = _make_quick_review(client)
    _age_review(rid, created="2026-10-01T12:00:00",
                updated="2026-10-08T11:59:59")  # 1 second short of 7 days
    q = _quests(client)["RF-04"]
    assert q["status"] == "active"
    assert q["progress_current"] == 0
    assert q["completed_at"] is None
    assert q["claimable"] is False


def test_rf04_completed_exactly_at_7_day_boundary(client):
    seed_settings(client)
    rid = _make_quick_review(client)
    _age_review(rid, created="2026-10-01T12:00:00",
                updated="2026-10-08T12:00:00")  # exactly 7 days -> counts
    q = _quests(client)["RF-04"]
    assert q["progress_current"] == 1
    assert q["completed_at"] is not None
    assert q["claimable"] is True


def test_rf04_completed_after_7_days_and_claim_once(client):
    seed_settings(client)
    rid = _make_quick_review(client)
    _age_review(rid, created="2026-10-01T12:00:00",
                updated="2026-10-20T09:00:00")
    # editing the review awarded no XP at any point
    assert xp_total(client) == 35  # trade +20, quick review +15, edit +0
    q = _quests(client)["RF-04"]
    assert q["completed_at"] is not None and q["claimed_at"] is None
    r = _claim(client, "RF-04")
    assert r.status_code == 200
    assert r.json()["awarded_xp"] == 25
    assert xp_total(client) == 60
    # duplicate claim -> 409, no second award
    assert _claim(client, "RF-04").status_code == 409
    assert xp_total(client) == 60


def test_rf04_daily_and_weekly_reviews_also_count(client):
    seed_settings(client)
    import datetime as dt

    from app2.db import SessionLocal
    from app2.models import DailyReview
    client.post("/api/daily-reviews/2026-10-01", json={"energy": 3})
    with SessionLocal() as db:
        row = db.query(DailyReview).first()
        row.created_at = dt.datetime(2026, 10, 1, 8, 0)
        row.updated_at = dt.datetime(2026, 10, 15, 8, 0)
        db.commit()
    assert _quests(client)["RF-04"]["completed_at"] is not None


def test_lq03_requires_four_weekly_reviews_with_advice(client):
    seed_settings(client)
    # historical / no advice -> never counted
    for wk in ("2026-W36", "2026-W37", "2026-W38", "2026-W39"):
        r = client.post(f"/api/weekly-reviews/{wk}", json={"highlights": "h"})
        assert r.status_code == 201
        assert r.json()["advice_to_future_me"] is None
    assert _quests(client)["LQ-03"]["progress_current"] == 0

    # blank advice is normalised to None -> not counted
    r = client.patch("/api/weekly-reviews/2026-W36",
                     json={"advice_to_future_me": "   "})
    assert r.status_code == 200
    assert r.json()["advice_to_future_me"] is None

    # three with advice -> progress 3, not completed
    for wk in ("2026-W36", "2026-W37", "2026-W38"):
        r = client.patch(f"/api/weekly-reviews/{wk}",
                         json={"advice_to_future_me": "stay patient"})
        assert r.status_code == 200
        assert r.json()["advice_to_future_me"] == "stay patient"
    q = _quests(client)["LQ-03"]
    assert q["progress_current"] == 3
    assert q["completed_at"] is None

    # fourth -> completed, claim once (+50), duplicate claim rejected
    client.patch("/api/weekly-reviews/2026-W39",
                 json={"advice_to_future_me": "review before revenge"})
    q = _quests(client)["LQ-03"]
    assert q["progress_current"] == 4
    assert q["completed_at"] is not None
    assert q["claimable"] is True
    r = _claim(client, "LQ-03")
    assert r.status_code == 200 and r.json()["awarded_xp"] == 50
    assert _claim(client, "LQ-03").status_code == 409
    # 4 weekly reviews (+30 each = 120) + 50 quest reward
    assert xp_total(client) == 170


def test_lq03_advice_on_create_and_read_roundtrip(client):
    seed_settings(client)
    r = client.post("/api/weekly-reviews/2026-W40", json={
        "advice_to_future_me": "never add to a loser",
    })
    assert r.status_code == 201
    assert r.json()["xp_awarded"] == 30
    body = client.get("/api/weekly-reviews/2026-W40").json()
    assert body["advice_to_future_me"] == "never add to a loser"


def test_no_quest_requires_risk_or_trade_frequency(client):
    """All quest conditions are journaling/reflection based - inspection test."""
    from app2.services.quests import QUEST_CATALOG
    forbidden = ("volume", "risk", "pnl", "profit", "win_rate", "lot")
    for q in QUEST_CATALOG:
        blob = (q.name + q.description).lower()
        for word in forbidden:
            assert word not in blob, f"{q.code} mentions {word}"


def test_lq02_not_keyword_matching():
    """LQ-02 is DEFERRED (uses no fuzzy keyword condition at all)."""
    from app2.services.quests import QUESTS_BY_CODE
    q = QUESTS_BY_CODE["LQ-02"]
    assert q.status == "deferred" and q.condition == ""
