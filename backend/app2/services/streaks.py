"""Streak Break & Recovery service.

Approved semantics (implementation specification):

* A **qualifying active day** is a LOCAL calendar day with at least one of the
  six approved journaling/learning activities: Daily Review, Weekly Review, Quick
  Review, Deep Review, Lesson, Emotional Journal Entry.  Trade capture, trade
  close, edits, P&L changes and duplicates never qualify, and a day counts at
  most once.  Streak days themselves award **0 XP**.
* A break is eligible only when the previous run reached ``STREAK_MIN_DAYS`` (3).
* **Yesterday-grace**: the streak survives a missed *today*; a break is only
  considered once today *and* yesterday are both inactive.
* Recovery needs ``STREAK_RECOVERY_TARGET_DAYS`` (2) distinct qualifying active
  local days on or after the break date.
* Tracking starts at an activation baseline - historical activity is never
  backfilled and never produces retroactive breaks.

Timezone strategy
-----------------
``TimestampMixin.created_at`` is stored as **naive UTC** (``server_default=
func.now()``), while the rest of the app stores naive local wall-clock time.
Explicit local-date columns are always preferred:

===================  ================================
Activity             Local date source
===================  ================================
Daily Review         ``review_date``      (explicit)
Emotional Entry      ``local_date``       (explicit)
Weekly Review        ``created_at`` -> UTC->local
Quick Review         ``created_at`` -> UTC->local
Deep Review          ``created_at`` -> UTC->local
Lesson               ``created_at`` -> UTC->local
===================  ================================

``created_at`` is *never* read as local wall-clock, so an activity just after
midnight local time is filed on the correct day.

Known limitation
----------------
The database stores no timezone identifier, so conversion uses the *server's*
current local timezone.  If the machine's timezone changes, day attribution of
past UTC timestamps can shift.  Nothing is rewritten; this is documented rather
than silently assumed away.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from .. import config
from ..models import (
    AppMeta,
    DailyReview,
    DeepReview,
    EmotionalEntry,
    Lesson,
    QuickReview,
    StreakEvent,
    StreakQuestClaim,
    StreakReflection,
    UiPreference,
    WeeklyReview,
)

_ONE_DAY = dt.timedelta(days=1)


def utc_to_local_date(value: dt.datetime | None) -> dt.date | None:
    """Convert a stored naive-UTC ``created_at`` to its LOCAL calendar date.

    ``created_at`` is naive UTC by definition.  It is tagged as UTC and
    converted - never read as local wall-clock.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone().date()  # defensive: already authoritative
    return value.replace(tzinfo=dt.timezone.utc).astimezone().date()


def qualifying_active_dates(
    db: Session, *, since: dt.date | None = None
) -> set[dt.date]:
    """Set of LOCAL dates holding at least one approved qualifying activity.

    ``since`` applies the activation baseline: nothing before it is ever
    considered (spec F - no historical backfill).
    """
    dates: set[dt.date] = set()

    def add(day: dt.date | None) -> None:
        if day is None:
            return
        if since is not None and day < since:
            return
        dates.add(day)

    # explicit local-date columns (preferred)
    for (day,) in db.query(DailyReview.review_date).all():
        add(day)
    for (day,) in db.query(EmotionalEntry.local_date).all():
        add(day)

    # UTC stored timestamps, converted to local before use
    for model in (WeeklyReview, QuickReview, DeepReview, Lesson):
        for (created,) in db.query(model.created_at).all():
            add(utc_to_local_date(created))

    return dates


# --- pure streak maths (deterministic, unit-testable) ----------------------
def run_ending_at(active: set[dt.date], last_day: dt.date) -> int:
    """Length of the consecutive active run whose FINAL day is ``last_day``."""
    if last_day not in active:
        return 0
    length = 0
    cursor = last_day
    while cursor in active:
        length += 1
        cursor -= _ONE_DAY
    return length


def current_streak(active: set[dt.date], today: dt.date) -> int:
    """Consecutive active days ending today **or** yesterday (yesterday-grace).

    Missing only today never reduces the streak to zero.
    """
    if today in active:
        return run_ending_at(active, today)
    yesterday = today - _ONE_DAY
    if yesterday in active:
        return run_ending_at(active, yesterday)
    return 0

# --- opt-in + activation baseline -------------------------------------------
def is_enabled(db: Session) -> bool:
    """Tracking is ON by default: an absent preference row means enabled."""
    row = db.query(UiPreference).filter(
        UiPreference.key == config.STREAK_PREF_KEY).first()
    if row is None:
        return True
    return str(row.value).strip().lower() not in {"false", "0", "off", "no"}


def _meta(db: Session, key: str) -> str | None:
    row = db.query(AppMeta).filter(AppMeta.key == key).first()
    return row.value if row else None


def _set_meta(db: Session, key: str, value: str | None) -> None:
    row = db.query(AppMeta).filter(AppMeta.key == key).first()
    if row is None:
        if value is not None:
            db.add(AppMeta(key=key, value=value))
        return
    row.value = value


def ensure_baseline(db: Session) -> dt.date | None:
    """Return the activation baseline, creating/resetting it as approved.

    * First ever run  -> baseline = today (no historical backfill).
    * User disables   -> ``disabled_at`` stamped; nothing is evaluated.
    * User re-enables -> a NEW baseline is set to today, so the disabled period
      can never produce retroactive breaks.
    * Otherwise       -> the stored baseline is returned unchanged, so restarts
      never move the starting point.
    """
    today = config.today_local()
    if not is_enabled(db):
        if _meta(db, config.STREAK_META_DISABLED_AT) is None:
            _set_meta(db, config.STREAK_META_DISABLED_AT, today.isoformat())
        return None

    raw = _meta(db, config.STREAK_META_SINCE)
    if _meta(db, config.STREAK_META_DISABLED_AT) is not None:
        _set_meta(db, config.STREAK_META_SINCE, today.isoformat())
        _set_meta(db, config.STREAK_META_DISABLED_AT, None)
        return today
    if raw is None:
        _set_meta(db, config.STREAK_META_SINCE, today.isoformat())
        return today
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        _set_meta(db, config.STREAK_META_SINCE, today.isoformat())
        return today


# --- detection --------------------------------------------------------------
def evaluate(db: Session) -> StreakEvent | None:
    """Detect (and idempotently persist) a streak break if one is due.

    Returns the newest event still needing recovery, or None.  Safe to call on
    every request: repeated evaluation never duplicates an event, a reflection,
    an XP entry or an achievement.
    """
    # ``ensure_baseline`` also stamps the "disabled at" marker when tracking is
    # off, so it must run even while disabled (it returns None then).
    baseline = ensure_baseline(db)
    if baseline is None:
        return None  # tracking disabled: nothing calculated or recorded
    today = config.today_local()
    active = qualifying_active_dates(db, since=baseline)

    eligible, length, broke_on = break_is_eligible(active, today)
    if eligible and broke_on is not None:
        _record_break(db, today=today, broke_on=broke_on, streak_length=length)
        db.flush()
    # Refresh recovery completion for every open event so RC-02 and the recovery
    # achievement observe up-to-date state on ANY endpoint that runs the
    # progress engine (not only when the Quest Hub happens to be read).
    for open_event in (db.query(StreakEvent)
                       .filter(StreakEvent.recovery_done_at.is_(None))
                       .order_by(StreakEvent.detected_on.desc()).all()):
        event_progress(db, open_event)
    return _latest_unfinished(db)


def _record_break(
    db: Session, *, today: dt.date, broke_on: dt.date, streak_length: int
) -> StreakEvent | None:
    """Insert one break event.  Database UNIQUE constraints are the firewall."""
    existing = db.query(StreakEvent).filter(
        StreakEvent.broke_on == broke_on).first()
    if existing is not None:
        return existing  # same gap already processed - never re-processed
    detected = db.query(StreakEvent).filter(
        StreakEvent.detected_on == today).first()
    if detected is not None:
        return detected
    event = StreakEvent(
        broke_on=broke_on,
        detected_on=today,
        streak_length=int(streak_length),
        recovery_target=config.STREAK_RECOVERY_TARGET_DAYS,
    )
    db.add(event)
    db.flush()
# --- lifecycle --------------------------------------------------------------
def event_progress(db: Session, event: StreakEvent) -> dict:
    """Reflect/recovery progress for one event, derived from real records."""
    today = config.today_local()
    baseline = ensure_baseline(db)
    active = qualifying_active_dates(db, since=baseline)

    recovery_days = sorted(d for d in active if d >= event.detected_on)
    target = int(event.recovery_target or config.STREAK_RECOVERY_TARGET_DAYS)
    recovery_current = min(len(recovery_days), target)
    if event.recovery_done_at is None and recovery_current >= target:
        event.recovery_done_at = config.now_local()
        db.flush()
    recovery_done = event.recovery_done_at is not None
    reflection_done = event.reflection_done_at is not None

    if reflection_done and recovery_done:
        stage = "badge_unlocked"
    elif recovery_done:
        stage = "recovery_done"
    elif reflection_done:
        stage = "reflection_done"
    else:
        stage = "detected"

    reflection = db.query(StreakReflection).filter(
        StreakReflection.event_id == event.id).first()
    return {
        "id": event.id,
        "broke_on": event.broke_on.isoformat(),
        "detected_on": event.detected_on.isoformat(),
        "streak_length": int(event.streak_length or 0),
        "stage": stage,
        "reflection_done": reflection_done,
        "recovery_target": target,
        "recovery_current": recovery_current,
        "recovery_done": recovery_done,
        "recovery_days": [d.isoformat() for d in recovery_days[:target]],
        "alert_seen_at": (event.alert_seen_at.isoformat()
                          if event.alert_seen_at else None),
        "reflection": ({
            "obstacle": reflection.obstacle,
            "resume_step": reflection.resume_step,
        } if reflection else None),
        "as_of": today.isoformat(),
    }


def save_reflection(
    db: Session, event: StreakEvent, *, obstacle: str | None,
    resume_step: str | None,
) -> dict:
    """Create-or-update the single reflection for an event.

    Re-saving never creates a second row and never re-awards XP: the quest claim
    path owns the reward and is idempotent on its own.
    """
    row = db.query(StreakReflection).filter(
        StreakReflection.event_id == event.id).first()
    if row is None:
        row = StreakReflection(event_id=event.id)
        db.add(row)
    row.obstacle = obstacle
    row.resume_step = resume_step
    if event.reflection_done_at is None:
        event.reflection_done_at = config.now_local()
    db.flush()
    return event_progress(db, event)


def mark_alert_seen(db: Session, event: StreakEvent) -> None:
    if event.alert_seen_at is None:
        event.alert_seen_at = config.now_local()
        db.flush()


def completed_reflection_count(db: Session) -> int:
    return int(db.query(StreakEvent).filter(
        StreakEvent.reflection_done_at.isnot(None)).count())


def completed_recovery_count(db: Session) -> int:
    return int(db.query(StreakEvent).filter(
        StreakEvent.recovery_done_at.isnot(None)).count())


def claim_streak_quest(db: Session, quest_code: str) -> dict:
    """Claim RC-01 / RC-02 for every event that earned it but has not claimed.

    Returns ``{"awarded_xp": total, "event_ids": [...]}``.  Safe under retries,
    restarts and concurrency: the ledger's UNIQUE idempotency key and the
    ``streak_quest_claims`` UNIQUE(event_id, quest_code) constraint both prevent
    a second award for the same event.
    """
    from . import xp as xp_service

    stage_field = (
        StreakEvent.reflection_done_at if quest_code == "RC-01"
        else StreakEvent.recovery_done_at
    )
    events = (
        db.query(StreakEvent)
        .filter(stage_field.isnot(None))
        .order_by(StreakEvent.detected_on.asc())
        .all()
    )
    awarded = 0
    claimed_ids: list[int] = []
    for event in events:
        if _already_claimed(db, event.id, quest_code):
            continue
        amount = xp_service.award_streak_quest_xp(
            db, event_id=event.id, quest_code=quest_code,
            amount=config.STREAK_RECOVERY_XP[quest_code],
        )
        if amount == 0:  # ledger key existed (concurrent claim won the race)
            continue
        db.add(StreakQuestClaim(
            event_id=event.id,
            quest_code=quest_code,
            idempotency_key=xp_service.streak_quest_key(event.id, quest_code),
            claimed_at=config.now_local(),
        ))
        awarded += amount
        claimed_ids.append(event.id)
    db.flush()
    return {"awarded_xp": awarded, "event_ids": claimed_ids}


def _already_claimed(db: Session, event_id: int, quest_code: str) -> bool:
    return db.query(StreakQuestClaim).filter(
        StreakQuestClaim.event_id == event_id,
        StreakQuestClaim.quest_code == quest_code,
    ).first() is not None


def pending_claim_events(db: Session, quest_code: str) -> list[int]:
    """Event ids that completed this stage but have not claimed its reward."""
    stage_field = (
        StreakEvent.reflection_done_at if quest_code == "RC-01"
        else StreakEvent.recovery_done_at
    )
    out: list[int] = []
    for event in (
        db.query(StreakEvent).filter(stage_field.isnot(None))
        .order_by(StreakEvent.detected_on.asc()).all()
    ):
        if not _already_claimed(db, event.id, quest_code):
            out.append(event.id)
    return out


def latest_claim_time(db: Session, quest_code: str):
    row = (
        db.query(StreakQuestClaim)
        .filter(StreakQuestClaim.quest_code == quest_code)
        .order_by(StreakQuestClaim.claimed_at.desc())
        .first()
    )
    return row.claimed_at if row else None


def claimed_event_count(db: Session, quest_code: str) -> int:
    return int(db.query(StreakQuestClaim)
               .filter(StreakQuestClaim.quest_code == quest_code).count())


def latest_event(db: Session) -> StreakEvent | None:
    return (db.query(StreakEvent)
            .order_by(StreakEvent.detected_on.desc()).first())


def state(db: Session) -> dict:
    """Serializable streak summary for the dashboard / Quest Hub."""
    # Always run the baseline bookkeeping first so the disabled/disabled-at
    # markers are maintained no matter which entry point is used.
    baseline = ensure_baseline(db)
    enabled = is_enabled(db)
    baseline_raw = _meta(db, config.STREAK_META_SINCE)
    if not enabled:
        return {
            "enabled": False,
            "baseline": baseline_raw,
            "current_streak": 0,
            "min_days": config.STREAK_MIN_DAYS,
            "recovery_target": config.STREAK_RECOVERY_TARGET_DAYS,
            "active_event": None,
            "message": "Streak tracking is paused. Existing records are kept.",
        }
    today = config.today_local()
    active = qualifying_active_dates(db, since=baseline)
    event = latest_event(db)
    return {
        "enabled": True,
        "baseline": baseline.isoformat() if baseline else None,
        "current_streak": current_streak(active, today),
        "min_days": config.STREAK_MIN_DAYS,
        "recovery_target": config.STREAK_RECOVERY_TARGET_DAYS,
        "active_event": event_progress(db, event) if event else None,
        "message": None,
    }
    return event


def _latest_unfinished(db: Session) -> StreakEvent | None:
    return (
        db.query(StreakEvent)
        .filter(StreakEvent.recovery_done_at.is_(None))
        .order_by(StreakEvent.detected_on.desc())
        .first()
    )

def break_is_eligible(
    active: set[dt.date], today: dt.date
) -> tuple[bool, int, dt.date | None]:
    """Evaluate the approved break rule.

    Returns ``(eligible, streak_length, broke_on)`` where ``broke_on`` is the
    final active day of the run that just ended.  Eligible only when today AND
    yesterday are inactive (never at midnight or after a single missed day)
    **and** the ended run reached ``STREAK_MIN_DAYS``.
    """
    yesterday = today - _ONE_DAY
    if today in active or yesterday in active:
        return False, 0, None
    last_active = yesterday - _ONE_DAY
    length = run_ending_at(active, last_active)
    if length < config.STREAK_MIN_DAYS:
        return False, length, None
    return True, length, last_active