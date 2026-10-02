"""Streak Break & Recovery - backend tests.

Every test runs against the disposable temporary database configured by
``tests_v2/conftest.py``.  The real user databases are never opened.

Time control: streak logic is driven by *local calendar dates*, so these tests
monkeypatch ``app2.config.today_local`` to walk the calendar deterministically
instead of sleeping or touching the clock.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app2 import config
from app2.models import AppMeta, StreakEvent
from tests_v2.conftest import seed_settings, xp_total

BASE = dt.date(2026, 3, 1)


def _day(n: int) -> dt.date:
    return BASE + dt.timedelta(days=n)


@pytest.fixture()
def clock(monkeypatch):
    """A movable 'today' for the streak service."""
    state = {"today": BASE}

    def _today():
        return state["today"]

    monkeypatch.setattr(config, "today_local", _today)
    monkeypatch.setattr(
        config, "now_local",
        lambda: dt.datetime.combine(state["today"], dt.time(12, 0)))
    return state


def _set_baseline(db_session, day: dt.date) -> None:
    """Pin the activation baseline so tests do not depend on the real clock."""
    row = db_session.query(AppMeta).filter(
        AppMeta.key == config.STREAK_META_SINCE).first()
    if row is None:
        db_session.add(
            AppMeta(key=config.STREAK_META_SINCE, value=day.isoformat()))
    else:
        row.value = day.isoformat()
    db_session.flush()


def _daily_review(db_session, day: dt.date) -> None:
    from app2.models import DailyReview

    db_session.add(DailyReview(review_date=day, reflection=f"day {day}"))
    db_session.flush()


def _emotional(db_session, day: dt.date) -> None:
    from app2.models import EmotionalEntry

    db_session.add(EmotionalEntry(
        local_date=day, occurred_at=dt.datetime.combine(day, dt.time(9, 0)),
        emotion_label="calm", intensity=3))
    db_session.flush()


def _active_run(db_session, start: int, length: int) -> None:
    for offset in range(length):
        _daily_review(db_session, _day(start + offset))


# =========================================================================
# pure streak maths
# =========================================================================
def test_run_and_current_streak_maths():
    from app2.services import streaks

    active = {_day(0), _day(1), _day(2)}
    assert streaks.current_streak(active, _day(2)) == 3
    # yesterday-grace: today inactive, yesterday active -> still 3
    assert streaks.current_streak(active, _day(3)) == 3
    # two inactive days -> 0
    assert streaks.current_streak(active, _day(4)) == 0
    assert streaks.run_ending_at(active, _day(2)) == 3
    assert streaks.run_ending_at(active, _day(3)) == 0


def test_break_needs_both_today_and_yesterday_inactive():
    from app2.services import streaks

    active = {_day(0), _day(1), _day(2)}
    # today inactive, yesterday active -> NOT a break (yesterday-grace)
    assert streaks.break_is_eligible(active, _day(3))[0] is False
    ok, length, broke_on = streaks.break_is_eligible(active, _day(4))
    assert ok is True
    assert length == 3
    assert broke_on == _day(2)


def test_short_streak_never_breaks():
    from app2.services import streaks

    ok, length, _ = streaks.break_is_eligible({_day(0), _day(1)}, _day(5))
    assert ok is False
    assert length < config.STREAK_MIN_DAYS


def test_never_established_streak_never_breaks():
    from app2.services import streaks

    ok, _length, broke_on = streaks.break_is_eligible(set(), _day(9))
    assert ok is False
    assert broke_on is None


def test_activity_after_break_starts_a_new_streak():
    from app2.services import streaks

    active = {_day(0), _day(1), _day(2), _day(6), _day(7)}
    assert streaks.current_streak(active, _day(7)) == 2
    # yesterday is active -> grace, not a break
    assert streaks.break_is_eligible(active, _day(8))[0] is False


def test_utc_created_at_is_not_read_as_local():
    """A naive-UTC timestamp late in the UTC day belongs to the NEXT local day."""
    from app2.services import streaks

    naive_utc = dt.datetime(2026, 3, 1, 21, 30)
    expected = naive_utc.replace(tzinfo=dt.timezone.utc).astimezone().date()
    assert streaks.utc_to_local_date(naive_utc) == expected
    assert streaks.utc_to_local_date(None) is None


def test_trade_activity_does_not_create_active_days(db_session, clock):
    """Trade capture is NOT a qualifying activity."""
    from app2.models import Trade
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    db_session.add(Trade(
        symbol_label="X", opened_at=dt.datetime.combine(_day(0), dt.time(10))))
    db_session.flush()
    assert streaks.qualifying_active_dates(db_session, since=BASE) == set()


def test_multiple_activities_one_day_count_once(db_session, clock):
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _daily_review(db_session, _day(0))
    _emotional(db_session, _day(0))
    assert streaks.qualifying_active_dates(db_session, since=BASE) == {_day(0)}


def test_created_at_based_activities_are_read(db_session, clock):
    """Quick/Deep/Lesson/Weekly qualify via their UTC created_at."""
    from app2.models import DeepReview, Lesson, QuickReview, Trade, WeeklyReview
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    trade = Trade(symbol_label="X",
                  opened_at=dt.datetime.combine(_day(0), dt.time(9)))
    db_session.add(trade)
    db_session.flush()
    db_session.add(QuickReview(trade_id=trade.id, execution_rating=3))
    db_session.add(DeepReview(trade_id=trade.id, mistakes="m"))
    db_session.add(Lesson(source_type="deep", text="lesson text"))
    db_session.add(WeeklyReview(iso_year=2026, iso_week=1, highlights="h"))
    db_session.flush()
    active = streaks.qualifying_active_dates(db_session, since=BASE)
    assert db_session.query(QuickReview).count() == 1
    assert db_session.query(WeeklyReview).count() == 1
    # all four land on one local day -> exactly one active date
    assert len(active) == 1


# =========================================================================
# detection + idempotency
# =========================================================================
def test_break_event_recorded_once_across_repeated_evaluation(db_session, clock):
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(4)  # days 3 and 4 inactive
    first = streaks.evaluate(db_session)
    assert first is not None
    assert first.streak_length == 3
    for _ in range(5):
        streaks.evaluate(db_session)
        db_session.flush()
    assert db_session.query(StreakEvent).count() == 1


def test_no_break_event_before_both_days_inactive(db_session, clock):
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(3)  # only today inactive -> yesterday-grace
    assert streaks.evaluate(db_session) is None
    assert db_session.query(StreakEvent).count() == 0


def test_second_day_inactive_records_the_break(db_session, clock):
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(4)
    assert streaks.evaluate(db_session) is not None
    assert db_session.query(StreakEvent).count() == 1


def test_short_streak_records_no_event(db_session, clock):
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 2)
    clock["today"] = _day(6)
    assert streaks.evaluate(db_session) is None
    assert db_session.query(StreakEvent).count() == 0


def test_historical_activity_is_not_backfilled(db_session, clock):
    from app2.services import streaks

    _active_run(db_session, -20, 3)  # old history before activation
    _set_baseline(db_session, BASE)
    clock["today"] = _day(5)
    streaks.evaluate(db_session)
    assert db_session.query(StreakEvent).count() == 0


def test_independent_second_break_gets_its_own_event(db_session, clock):
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(4)
    streaks.evaluate(db_session)
    _active_run(db_session, 5, 3)
    clock["today"] = _day(9)
    streaks.evaluate(db_session)
# =========================================================================
# opt-in + baseline
# =========================================================================
def test_tracking_enabled_by_default(db_session):
    from app2.services import streaks

    assert streaks.is_enabled(db_session) is True


def test_disabled_tracking_creates_no_events(db_session, clock):
    from app2.models import UiPreference
    from app2.services import streaks

    db_session.add(UiPreference(key=config.STREAK_PREF_KEY, value="false"))
    db_session.flush()
    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(4)
    assert streaks.evaluate(db_session) is None
    assert db_session.query(StreakEvent).count() == 0


def test_disabled_tracking_preserves_existing_records(db_session, clock):
    from app2.models import UiPreference
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(4)
    streaks.evaluate(db_session)
    assert db_session.query(StreakEvent).count() == 1

    db_session.add(UiPreference(key=config.STREAK_PREF_KEY, value="false"))
    db_session.flush()
    streaks.evaluate(db_session)
    assert db_session.query(StreakEvent).count() == 1


def test_reenable_establishes_new_baseline_without_retroactive_break(
    db_session, clock
):
    from app2.models import UiPreference
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    db_session.add(UiPreference(key=config.STREAK_PREF_KEY, value="false"))
    db_session.flush()
    streaks.evaluate(db_session)  # stamps disabled_at
    row = db_session.query(UiPreference).filter(
        UiPreference.key == config.STREAK_PREF_KEY).first()
    row.value = "true"
    db_session.flush()

    _active_run(db_session, 0, 3)  # gap inside the disabled window
    clock["today"] = _day(6)
    streaks.evaluate(db_session)
    assert db_session.query(StreakEvent).count() == 0
    assert streaks.ensure_baseline(db_session) == _day(6)


def test_baseline_is_stable_across_restarts(db_session, clock):
    from app2.services import streaks

    clock["today"] = _day(0)
    first = streaks.ensure_baseline(db_session)
    db_session.commit()
    clock["today"] = _day(2)
    assert streaks.ensure_baseline(db_session) == first


# =========================================================================
# reflection (RC-01)
# =========================================================================
def _make_break(db_session, clock):
    """Build a 3-day streak then two inactive days -> exactly one break event."""
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(4)
    event = streaks.evaluate(db_session)
    assert event is not None
    return event


# =========================================================================
# recovery (RC-02)
# =========================================================================
def test_one_recovery_day_gives_partial_progress(db_session, clock):
    from app2.services import streaks

    event = _make_break(db_session, clock)
    _daily_review(db_session, _day(5))
    clock["today"] = _day(5)
    progress = streaks.event_progress(db_session, event)
    assert progress["recovery_current"] == 1
    assert progress["recovery_done"] is False
    assert progress["stage"] == "detected"


def test_two_distinct_days_complete_recovery(db_session, clock):
    from app2.services import streaks

    event = _make_break(db_session, clock)
    _daily_review(db_session, _day(5))
    _daily_review(db_session, _day(6))
    clock["today"] = _day(6)
    progress = streaks.event_progress(db_session, event)
    assert progress["recovery_current"] == 2
    assert progress["recovery_done"] is True


def test_multiple_activities_same_day_count_as_one_recovery_day(
    db_session, clock
):
    from app2.services import streaks

    event = _make_break(db_session, clock)
    _daily_review(db_session, _day(5))
    _emotional(db_session, _day(5))
    clock["today"] = _day(5)
    assert streaks.event_progress(db_session, event)["recovery_current"] == 1


def test_trade_only_activity_does_not_advance_recovery(db_session, clock):
    from app2.models import Trade
    from app2.services import streaks

    event = _make_break(db_session, clock)
    db_session.add(Trade(
        symbol_label="X", opened_at=dt.datetime.combine(_day(5), dt.time(10))))
    db_session.flush()
    clock["today"] = _day(5)
    assert streaks.event_progress(db_session, event)["recovery_current"] == 0


def test_activity_before_break_date_does_not_count(db_session, clock):
    from app2.services import streaks

    event = _make_break(db_session, clock)
    clock["today"] = _day(4)  # days 0-2 precede detected_on
    assert streaks.event_progress(db_session, event)["recovery_current"] == 0


def test_recovery_completion_is_idempotent(db_session, clock):
    from app2.services import streaks

    event = _make_break(db_session, clock)
    _active_run(db_session, 5, 2)
    clock["today"] = _day(6)
    for _ in range(4):
        assert streaks.event_progress(db_session, event)["recovery_done"] is True
        db_session.flush()
    assert db_session.query(StreakEvent).filter(
        StreakEvent.recovery_done_at.isnot(None)).count() == 1


def test_lifecycle_reaches_badge_unlocked(db_session, clock):
    from app2.services import streaks

    event = _make_break(db_session, clock)
    streaks.save_reflection(db_session, event, obstacle="x", resume_step="y")
    _active_run(db_session, 5, 2)
    clock["today"] = _day(6)
    progress = streaks.event_progress(db_session, event)
    assert progress["stage"] == "badge_unlocked"
    assert progress["reflection_done"] and progress["recovery_done"]
    assert event is not None
    return event


def test_saving_reflection_completes_rc01(db_session, clock):
    from app2.models import StreakReflection
    from app2.services import streaks

    event = _make_break(db_session, clock)
    progress = streaks.save_reflection(
        db_session, event, obstacle="busy week", resume_step="one review")
    assert progress["reflection_done"] is True
    assert progress["stage"] == "reflection_done"
    assert db_session.query(StreakReflection).count() == 1


def test_reflection_is_unique_per_event(db_session, clock):
    from app2.models import StreakReflection
    from app2.services import streaks

    event = _make_break(db_session, clock)
    for _ in range(3):
        streaks.save_reflection(
            db_session, event, obstacle="busy", resume_step="step")
        db_session.flush()
    assert db_session.query(StreakReflection).count() == 1


def test_editing_reflection_keeps_completion(db_session, clock):
    from app2.services import streaks

    event = _make_break(db_session, clock)
    first = streaks.save_reflection(
        db_session, event, obstacle="a", resume_step="b")
    edited = streaks.save_reflection(
        db_session, event, obstacle="a2", resume_step="b2")
    assert edited["reflection_done"] is True
    assert edited["reflection"]["obstacle"] == "a2"
    assert first["reflection_done"] == edited["reflection_done"]


def test_short_streak_creates_no_event(db_session, clock):
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 2)
    clock["today"] = _day(6)
    assert streaks.evaluate(db_session) is None
    assert streaks.latest_event(db_session) is None
    assert db_session.query(StreakEvent).count() == 0


def test_same_gap_is_not_reprocessed_on_a_later_day(db_session, clock):
    """The UNIQUE broke_on guard stops a historical gap becoming a new event."""
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(4)
    streaks.evaluate(db_session)
    for later in (5, 6, 7):
        clock["today"] = _day(later)
        streaks.evaluate(db_session)
        db_session.flush()
    assert db_session.query(StreakEvent).count() == 1


def test_current_streak_is_reported(db_session, clock):
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(2)
    state = streaks.state(db_session)
    assert state["enabled"] is True
    assert state["current_streak"] == 3
    assert state["min_days"] == 3
def test_explicit_local_date_fields_are_respected(db_session, clock):
    """Daily Review / Emotional Entry use their stored local date verbatim."""
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _daily_review(db_session, _day(1))
    _emotional(db_session, _day(2))
    assert streaks.qualifying_active_dates(db_session, since=BASE) == {
        _day(1), _day(2)}
# =========================================================================
# API surface, XP and the hidden recovery achievement
# =========================================================================
def _seed_break_via_db(db_session, clock):
    """Create an eligible break directly in the DB (session-scoped)."""
    from app2.services import streaks

    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    clock["today"] = _day(4)
    event = streaks.evaluate(db_session)
    db_session.commit()
    assert event is not None
    return event.id


def test_streak_endpoint_reports_state(client, db_session, clock):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    body = client.get("/api/streak").json()
    assert body["enabled"] is True
    assert body["min_days"] == 3
    assert body["recovery_target"] == 2
    assert body["active_event"]["streak_length"] == 3
    assert body["active_event"]["stage"] == "detected"
    assert body["active_event"]["reflection_done"] is False


def test_dashboard_exposes_streak_block(client, db_session, clock):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    body = client.get("/api/dashboard").json()
    assert "streak" in body
    assert body["streak"]["active_event"]["streak_length"] == 3


def test_reflection_endpoint_completes_rc01_and_awards_25_once(
    client, db_session, clock
):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    before = xp_total(client)

    r = client.put("/api/streak/reflection", json={
        "obstacle": "busy week", "resume_step": "one daily review"})
    assert r.status_code == 200
    assert r.json()["reflection_done"] is True

    quests = {q["code"]: q for q in client.get("/api/quests").json()["items"]}
    assert quests["RC-01"]["completed_at"] is not None
    assert quests["RC-01"]["claimable"] is True
    assert xp_total(client) == before  # completion alone awards nothing

    assert client.post("/api/quests/RC-01/claim").json()["awarded_xp"] == 25
    total = xp_total(client)
    assert total == before + 25
    assert client.post("/api/quests/RC-01/claim").status_code == 409
    assert xp_total(client) == total  # no duplicate XP


def test_reflection_edit_does_not_award_again(client, db_session, clock):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "a", "resume_step": "b"})
    client.post("/api/quests/RC-01/claim")
    total = xp_total(client)

    r = client.put("/api/streak/reflection", json={
        "obstacle": "edited", "resume_step": "edited step"})
    assert r.status_code == 200
    assert r.json()["reflection"]["obstacle"] == "edited"
    assert xp_total(client) == total


def test_repeated_reflection_submissions_do_not_duplicate(
    client, db_session, clock
):
    from app2.models import StreakReflection

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    for _ in range(4):
        client.put("/api/streak/reflection",
                   json={"obstacle": "x", "resume_step": "y"})
    with db_session:
        assert db_session.query(StreakReflection).count() == 1
    client.post("/api/quests/RC-01/claim")
    assert xp_total(client) == 25


def test_recovery_completes_after_two_days_and_awards_50_once(
    client, db_session, clock
):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)

def test_recovery_achievement_hidden_until_both_quests_complete(
    client, db_session, clock
):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)

    def ach():
        return {a["code"]: a for a in
                client.get("/api/achievements").json()["items"]}

    # reflection only -> still locked and hidden
    client.put("/api/streak/reflection",
               json={"obstacle": "x", "resume_step": "y"})
    entry = ach()["ACH-REC-PHOENIX"]
    assert entry["unlocked"] is False
    assert entry["hidden"] is True
    assert entry["name"] == "???"

    # reflection + recovery -> unlocked exactly once
    _active_run(db_session, 5, 2)
    db_session.commit()
    clock["today"] = _day(6)
    entry = ach()["ACH-REC-PHOENIX"]
    assert entry["unlocked"] is True
    assert entry["name"] == "Rising Phoenix"
    assert entry["unlocked_at"] is not None

    from app2.models import AchievementUnlock

    for _ in range(3):
        client.get("/api/achievements")
        client.get("/api/dashboard")
    with db_session:
        assert db_session.query(AchievementUnlock).filter(
            AchievementUnlock.code == "ACH-REC-PHOENIX").count() == 1


def test_achievement_seen_flag_follows_existing_convention(
    client, db_session, clock
):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection",
               json={"obstacle": "x", "resume_step": "y"})
    _active_run(db_session, 5, 2)
    db_session.commit()
    clock["today"] = _day(6)
    client.get("/api/achievements")

    before = {a["code"]: a for a in
              client.get("/api/achievements").json()["items"]}
    assert before["ACH-REC-PHOENIX"]["seen_at"] is None
    assert client.post(
        "/api/achievements/ACH-REC-PHOENIX/seen").status_code == 204
    after = {a["code"]: a for a in
             client.get("/api/achievements").json()["items"]}
    assert after["ACH-REC-PHOENIX"]["seen_at"] is not None
    assert (after["ACH-REC-PHOENIX"]["unlocked_at"]
            == before["ACH-REC-PHOENIX"]["unlocked_at"])


def test_streak_days_award_no_xp_and_break_deducts_nothing(
    client, db_session, clock
):
    from app2.models import XpEvent

    seed_settings(client)
    baseline_xp = xp_total(client)
    _active_run(db_session, 0, 3)
    db_session.commit()
    clock["today"] = _day(2)
    assert xp_total(client) == baseline_xp  # three active days, no XP

    clock["today"] = _day(4)
    client.get("/api/dashboard")  # detection runs
    assert xp_total(client) == baseline_xp
    with db_session:
        assert db_session.query(XpEvent).filter(XpEvent.amount < 0).count() == 0


def test_repeated_api_requests_do_not_duplicate_events(
    client, db_session, clock
):
    from app2.models import StreakEvent

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    for _ in range(5):
        client.get("/api/streak")
        client.get("/api/dashboard")
        client.get("/api/quests")
    with db_session:
        assert db_session.query(StreakEvent).count() == 1


def test_disabled_via_preference_stops_detection(client, db_session, clock):
    from app2.models import StreakEvent

    seed_settings(client)
    r = client.put("/api/preferences/streak_tracking_enabled",
                   json={"value": "false"})
    assert r.status_code == 200
    _set_baseline(db_session, BASE)
    _active_run(db_session, 0, 3)
    db_session.commit()
    clock["today"] = _day(4)
    assert client.get("/api/dashboard").json()["streak"]["enabled"] is False
    with db_session:
        assert db_session.query(StreakEvent).count() == 0


def test_reflection_without_event_returns_404(client):
    """No streak break yet -> a clear error, never a fabricated event."""
    seed_settings(client)
    r = client.put("/api/streak/reflection", json={"obstacle": "x"})
    assert r.status_code == 404
    assert "No streak break recorded yet" in r.json()["detail"]


def test_existing_quest_and_achievement_behaviour_unchanged(client):
    """The pre-existing catalog is untouched apart from the two new quests."""
    quests = {q["code"]: q for q in client.get("/api/quests").json()["items"]}
    assert quests["FT-01"]["reward_xp"] == 25
    assert quests["RF-01"]["reward_xp"] == 50
    assert quests["LQ-02"]["status"] == "deferred"
    assert quests["CN-01"]["opt_in"] is True
    assert quests["CN-01"]["reward_xp"] is None
    achs = {a["code"] for a in client.get("/api/achievements").json()["items"]}
    assert {"ACH-INIT-TRADE", "ACH-SECRET-PHOENIX",
            "ACH-REF-QUICK10"} <= achs


def test_recovery_quest_never_awarded_for_trade_only_activity(
    client, db_session, clock
):
    from app2.models import Trade

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    db_session.add(Trade(
        symbol_label="X", opened_at=dt.datetime.combine(_day(5), dt.time(10))))
    db_session.commit()
    clock["today"] = _day(5)
# =========================================================================
# Per-event rewards (RC-01 / RC-02 claimed once per streak-break event)
# =========================================================================
def _second_break(client, db_session, clock):
    """Complete RC-01 + RC-02 for a SECOND independent break.

    Uses days 8-10 for the new streak and 13-14 for its recovery so it never
    collides with the first break (days 0-2, break on day 4) or with an
    earlier recovery pair (days 5-6): ``daily_reviews.review_date`` is UNIQUE.
    """
    _active_run(db_session, 8, 3)     # a fresh 3-day streak
    db_session.commit()
    clock["today"] = _day(12)         # days 11 and 12 inactive -> second break
    client.get("/api/dashboard")
    client.put("/api/streak/reflection",
               json={"obstacle": "again", "resume_step": "smaller steps"})
    _active_run(db_session, 13, 2)    # 2 recovery days for the second event
    db_session.commit()
    clock["today"] = _day(14)
    client.get("/api/dashboard")      # persists recovery completion


def test_first_event_claims_25_and_50(client, db_session, clock):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    assert client.post("/api/quests/RC-01/claim").json()["awarded_xp"] == 25

    _active_run(db_session, 5, 2)
    db_session.commit()
    clock["today"] = _day(6)
    assert client.post("/api/quests/RC-02/claim").json()["awarded_xp"] == 50
    assert xp_total(client) == 75


def test_second_event_claims_its_own_25_and_50(client, db_session, clock):
    """The follow-up fix: a later break earns the rewards again."""
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    client.post("/api/quests/RC-01/claim")
    _active_run(db_session, 5, 2)
    db_session.commit()
    clock["today"] = _day(6)
    client.post("/api/quests/RC-02/claim")
    assert xp_total(client) == 75

    _second_break(client, db_session, clock)
    r1 = client.post("/api/quests/RC-01/claim")
    assert r1.status_code == 200
    assert r1.json()["awarded_xp"] == 25
    assert xp_total(client) == 100

    r2 = client.post("/api/quests/RC-02/claim")
    assert r2.status_code == 200
    assert r2.json()["awarded_xp"] == 50
    assert xp_total(client) == 150


def test_duplicate_rc01_claim_on_same_event_awards_nothing(
    client, db_session, clock
):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    assert client.post("/api/quests/RC-01/claim").json()["awarded_xp"] == 25
    total = xp_total(client)
    for _ in range(3):
        assert client.post("/api/quests/RC-01/claim").status_code == 409
    assert xp_total(client) == total


def test_duplicate_rc02_claim_on_same_event_awards_nothing(
    client, db_session, clock
):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    _active_run(db_session, 5, 2)
    db_session.commit()
    clock["today"] = _day(6)
    assert client.post("/api/quests/RC-02/claim").json()["awarded_xp"] == 50
    total = xp_total(client)
    for _ in range(3):
        assert client.post("/api/quests/RC-02/claim").status_code == 409
    assert xp_total(client) == total


def test_repeated_claims_across_restarts_do_not_duplicate(
    client, db_session, clock
):
    """Simulated restarts: fresh evaluation + fresh requests between claims."""
    from app2.models import StreakQuestClaim

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
def test_claim_rows_and_ledger_keys_are_unique_per_event(
    client, db_session, clock
):
    from app2.models import StreakQuestClaim, XpEvent

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    _second_break(client, db_session, clock)
    client.post("/api/quests/RC-01/claim")

    with db_session:
        claims = db_session.query(StreakQuestClaim).all()
        keys = [e.idempotency_key for e in db_session.query(XpEvent).all()]
    # two events -> two claim rows and two distinct per-event ledger keys
    assert len(claims) == 2
    assert len({(c.event_id, c.quest_code) for c in claims}) == 2
    streak_keys = [k for k in keys if k.startswith("streak:")]
    assert len(streak_keys) == 2
    assert set(streak_keys) == {f"streak:{c.event_id}:RC-01" for c in claims}


def test_database_constraints_reject_a_duplicate_claim_row(
    client, db_session, clock
):
    """The UNIQUE constraints are the hard firewall against duplicates."""
    from sqlalchemy.exc import IntegrityError

    from app2.models import StreakQuestClaim

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    client.post("/api/quests/RC-01/claim")
    existing = (
        db_session.query(StreakQuestClaim)
        .filter(StreakQuestClaim.quest_code == "RC-01").first()
    )
    db_session.add(StreakQuestClaim(
        event_id=existing.event_id,
        quest_code="RC-01",
        idempotency_key="streak:duplicate:RC-01",
        claimed_at=existing.claimed_at,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_ledger_idempotency_key_blocks_a_second_award(client, db_session, clock):
    """Even bypassing the claim table, the ledger's UNIQUE key returns 0."""
    from app2.services import streaks as streaks_service
    from app2.services import xp as xp_service

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    client.post("/api/quests/RC-01/claim")
    event_id = streaks_service.latest_event(db_session).id

    again = xp_service.award_streak_quest_xp(
        db_session, event_id=event_id, quest_code="RC-01", amount=25)
    assert again == 0
    assert streaks_service.claim_streak_quest(
        db_session, "RC-01")["awarded_xp"] == 0


def test_xp_and_dashboard_level_stay_consistent(client, db_session, clock):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    client.post("/api/quests/RC-01/claim")
    _active_run(db_session, 5, 2)
    db_session.commit()
    clock["today"] = _day(6)
    client.post("/api/quests/RC-02/claim")
    _second_break(client, db_session, clock)
    client.post("/api/quests/RC-01/claim")
    client.post("/api/quests/RC-02/claim")

    xp_api = client.get("/api/xp").json()
    pilot = client.get("/api/dashboard").json()["pilot"]
    assert xp_api["total_xp"] == pilot["total_xp"] == xp_total(client)
    assert xp_api["level"] == pilot["level"]
    assert xp_total(client) == 150  # two events x (25 + 50)


def test_no_negative_xp_entries_across_multiple_events(
    client, db_session, clock
):
    from app2.models import XpEvent

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    _active_run(db_session, 5, 2)
    db_session.commit()
    clock["today"] = _day(6)
    client.post("/api/quests/RC-01/claim")
    client.post("/api/quests/RC-02/claim")
    _second_break(client, db_session, clock)
    client.post("/api/quests/RC-01/claim")
    client.post("/api/quests/RC-02/claim")
    with db_session:
        assert db_session.query(XpEvent).filter(XpEvent.amount < 0).count() == 0


def test_phoenix_badge_still_unlocks_only_once(client, db_session, clock):
    """Per-event rewards must not multiply the globally-unlockable badge."""
    from app2.models import AchievementUnlock

    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    _active_run(db_session, 5, 2)
    db_session.commit()
    clock["today"] = _day(6)
    client.post("/api/quests/RC-01/claim")
    client.post("/api/quests/RC-02/claim")
    _second_break(client, db_session, clock)
    client.post("/api/quests/RC-01/claim")
    client.post("/api/quests/RC-02/claim")
    for _ in range(3):
        client.get("/api/achievements")

    entry = {a["code"]: a for a in
             client.get("/api/achievements").json()["items"]}["ACH-REC-PHOENIX"]
    assert entry["unlocked"] is True
    with db_session:
        assert db_session.query(AchievementUnlock).filter(
            AchievementUnlock.code == "ACH-REC-PHOENIX").count() == 1


def test_non_recovery_quests_keep_once_per_quest_behaviour(client):
    """FT-01 etc. are unaffected by the per-event change."""
    from tests_v2.conftest import make_trade

    seed_settings(client)
    make_trade(client)
    quests = {q["code"]: q for q in client.get("/api/quests").json()["items"]}
    assert quests["FT-01"]["claimable"] is True
    assert client.post("/api/quests/FT-01/claim").json()["awarded_xp"] == 25
    total = xp_total(client)
    assert client.post("/api/quests/FT-01/claim").status_code == 409
    assert xp_total(client) == total


def test_rc_claimable_reflects_pending_events(client, db_session, clock):
    seed_settings(client)
    _seed_break_via_db(db_session, clock)
    quests = {q["code"]: q for q in client.get("/api/quests").json()["items"]}
    assert quests["RC-01"]["claimable"] is False  # not completed yet

    client.put("/api/streak/reflection", json={"obstacle": "x", "resume_step": "y"})
    quests = {q["code"]: q for q in client.get("/api/quests").json()["items"]}
    assert quests["RC-01"]["claimable"] is True
    client.post("/api/quests/RC-01/claim")
    quests = {q["code"]: q for q in client.get("/api/quests").json()["items"]}
    assert quests["RC-01"]["claimable"] is False

    # a new break makes it claimable again
    _second_break(client, db_session, clock)
    quests = {q["code"]: q for q in client.get("/api/quests").json()["items"]}
    assert quests["RC-01"]["claimable"] is True