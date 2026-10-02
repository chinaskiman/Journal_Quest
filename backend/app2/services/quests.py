"""Quest catalog, evaluation and claim workflow.

Design notes (Phase 2 spec §11):

* Quest definitions live in a versioned code catalog - progress is always
  computed from real persisted database records, never from client counters.
* Evaluation and claiming are SEPARATE actions.  Marking a quest complete
  never awards XP; only the explicit claim endpoint does, atomically and
  idempotently (unique claim state + unique ledger key).
* DEFERRED quests: only ``LQ-02`` (recurring mistake pattern) remains
  deferred - it needs structured mistake tags (schema + product decision)
  and must NOT be faked with fuzzy keyword matching.  ``RF-04`` and
  ``LQ-03`` were activated in the approved Phase 2 correction pass:
  RF-04 ("Edit a completed review after >=7 days") uses the existing
  created_at/updated_at timestamps; LQ-03 ("advice-to-future-me in 4
  Weekly Reviews") uses the nullable ``advice_to_future_me`` column
  (historical NULL rows never count).
* Consistency quests (CN-01..03) are OPT-IN (disabled by default) and their
  reward amounts are UNDECIDED: configured as ``reward_xp=None`` which makes
  them completable but NOT claimable until values are decided.  Adding
  values later requires no schema or ledger change.
"""
from __future__ import annotations

import datetime as dt

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config
from ..models import (
    DailyReview,
    DeepReview,
    EmotionalEntry,
    Lesson,
    QuestProgress,
    QuickReview,
    Setup,
    Symbol,
    Trade,
    UiPreference,
    WeeklyReview,
)
from . import xp as xp_service

CATALOG_VERSION = 1  # bump when quest conditions change; claim keys include it


@dataclass(frozen=True)
class QuestDef:
    code: str
    name: str
    category: str
    description: str
    target: int
    reward_xp: int | None  # None => undecided / not claimable
    opt_in: bool = False
    status: str = "active"  # active | deferred
    condition: str = ""     # internal evaluator key


def _count(db: Session, model, *filters) -> int:
    q = db.query(func.coalesce(func.count(model.id), 0))
    for f in filters:
        q = q.filter(f)
    return int(q.scalar() or 0)


def _trades(db: Session) -> int:
    return _count(db, Trade, Trade.deleted_at.is_(None))


def _quick_reviews(db: Session) -> int:
    return _count(db, QuickReview)


def _deep_reviews(db: Session) -> int:
    return _count(db, DeepReview)


def _lessons(db: Session) -> int:
    return _count(db, Lesson)


def _linked_emotional(db: Session) -> int:
    return _count(db, EmotionalEntry, EmotionalEntry.trade_id.isnot(None))


def _first_symbol_and_setup(db: Session) -> int:
    return 1 if (_count(db, Symbol) >= 1 and _count(db, Setup) >= 1) else 0


def _total_xp_count(db: Session) -> int:
    return 1 if xp_service.total_xp(db) >= 100 else 0


def _distinct_daily_review_days(db: Session) -> int:
    return int(db.query(func.count(func.distinct(DailyReview.review_date))).scalar() or 0)


def _deep_lessons(db: Session) -> int:
    return _count(db, Lesson, Lesson.source_type == "deep")


_SEVEN_DAYS = dt.timedelta(days=7)


def _edits_after_7_days(db: Session) -> int:
    """RF-04 "Double Take": edit a completed review after >= 7 days.

    Blueprint condition (quest table): "Edit a completed review after
    >=7 days".  Verifiable from persisted data alone - a review counts when
    its ``updated_at`` is at least 7 days after its ``created_at`` (boundary
    inclusive).  ``updated_at`` only moves when an UPDATE actually persists,
    and the editing itself awards NO XP (PATCH never touches the ledger).
    All review types count (quick, deep, daily, weekly); emotional journal
    records are "entries", not reviews.
    """
    total = 0
    for model in (QuickReview, DeepReview, DailyReview, WeeklyReview):
        rows = db.query(model.created_at, model.updated_at).all()
        total += sum(
            1 for c, u in rows
            if c is not None and u is not None and (u - c) >= _SEVEN_DAYS
        )
    return total


def _weekly_advice(db: Session) -> int:
    """LQ-03 "Mentor Voice": advice-to-future-me written in 4 Weekly Reviews.

    Blueprint condition (quest table): "'Advice to future me' written in 4
    Weekly Reviews".  Only non-empty saved advice counts; historical rows
    (NULL, never back-filled) do not.
    """
    rows = db.query(WeeklyReview.advice_to_future_me).all()
    return sum(1 for (advice,) in rows if advice and advice.strip())


# --- streak break & recovery evaluators -------------------------------------
# These read persisted streak state only; detection lives in the streaks service
# and runs from the progress engine before quests are evaluated.
def _streak_reflections_done(db: Session) -> int:
    """RC-01: at least one streak-break reflection has been saved."""
    from . import streaks as streaks_service

    return streaks_service.completed_reflection_count(db)


def _streak_recoveries_done(db: Session) -> int:
    """RC-02: at least one streak break reached its recovery target."""
    from . import streaks as streaks_service

    return streaks_service.completed_recovery_count(db)


# --- catalog --------------------------------------------------------------
# Rewards use ONLY the tiers approved in the Blueprint QUEST TABLE
# (+25/+50/+75/+100): JM-01..04 = 25/50/75/100, so JM-03 "Log 50" = +75 is
# explicitly approved (the generic tier line elsewhere in the Blueprint
# says 25/50/100 - the specific quest table wins).  CN rewards are
# None = UNDECIDED (pending the user's decision - do not invent a value).

QUEST_CATALOG: list[QuestDef] = [
    QuestDef("FT-01", "First Contact", "first_time",
             "Create your first trade.", 1, 25, condition="trades"),
    QuestDef("FT-02", "First Reflection", "first_time",
             "Complete your first Quick Review.", 1, 25, condition="quick_reviews"),
    QuestDef("FT-03", "Deep Diver", "first_time",
             "Complete your first Deep Review.", 1, 25, condition="deep_reviews"),
    QuestDef("FT-04", "Heart on Sleeve", "first_time",
             "Write your first Emotional Journal entry.", 1, 25,
             condition="emotional_entries"),
    QuestDef("FT-05", "Day One", "first_time",
             "Complete your first Daily Review.", 1, 25, condition="daily_reviews"),
    QuestDef("FT-06", "Week One", "first_time",
             "Complete your first Weekly Review.", 1, 25, condition="weekly_reviews"),
    QuestDef("FT-07", "Chart Your World", "first_time",
             "Create your first symbol AND your first setup in Settings.", 1, 25,
             condition="first_symbol_and_setup"),
    QuestDef("RF-01", "Reflect x5", "reflection",
             "Complete Quick Reviews for 5 trades.", 5, 50, condition="quick_reviews"),
    QuestDef("RF-02", "Know Thyself", "reflection",
             "Link 3 emotional entries to trades.", 3, 50,
             condition="linked_emotional"),
    QuestDef("RF-03", "The Autopsy", "reflection",
             "Complete 5 Deep Reviews.", 5, 50, condition="deep_reviews"),
    QuestDef("RF-04", "Double Take", "reflection",
             "Edit a completed review at least 7 days after it was written.",
             1, 25, condition="edits_after_7_days"),
    QuestDef("JM-01", "Log 10", "milestone",
             "Log 10 trades.", 10, 25, condition="trades"),
    QuestDef("JM-02", "Log 25", "milestone",
             "Log 25 trades.", 25, 50, condition="trades"),
    QuestDef("JM-03", "Log 50", "milestone",
             "Log 50 trades.", 50, 75, condition="trades"),
    QuestDef("JM-04", "Log 100", "milestone",
             "Log 100 trades.", 100, 100, condition="trades"),
    QuestDef("JM-05", "Stargazer", "milestone",
             "Earn 100 total XP.", 1, 25, condition="total_xp_100"),
    QuestDef("JM-06", "Chronicler", "milestone",
             "Document 30 lessons.", 30, 50, condition="lessons"),
    QuestDef("CN-01", "Consistency 3", "consistency",
             "Complete Daily Reviews on 3 distinct days (opt-in).", 3, None,
             opt_in=True, condition="distinct_daily_days"),
    QuestDef("CN-02", "Consistency 7", "consistency",
             "Complete Daily Reviews on 7 distinct days (opt-in).", 7, None,
             opt_in=True, condition="distinct_daily_days"),
    QuestDef("CN-03", "Consistency 21", "consistency",
             "Complete Daily Reviews on 21 distinct days (opt-in).", 21, None,
             opt_in=True, condition="distinct_daily_days"),
    QuestDef("LQ-01", "Curious Mind", "learning",
             "Extract 5 lessons from Deep Reviews.", 5, 50,
             condition="deep_lessons"),
    QuestDef("LQ-02", "Pattern Breaker", "learning",
             "Recognise a recurring mistake and mark it worked-on.",
             1, 50, status="deferred", condition=""),
    QuestDef("LQ-03", "Mentor Voice", "learning",
             "Write advice-to-future-me in 4 Weekly Reviews.",
             4, 50, condition="weekly_advice"),
    # Streak Break & Recovery. Both activate when an eligible streak break is
    # recorded (see services/streaks.py). Rewards reuse approved existing tiers
    # (25 = bronze, 50 = silver); no new XP amount is invented. Claiming goes
    # through the normal idempotent quest-claim path, so XP is awarded once.
    QuestDef("RC-01", "Reflection Quest", "recovery",
             "After a streak break, save a short reflection on what got in the "
             "way and one small thing that would help you resume.",
             1, config.XP_STREAK_REFLECTION, condition="streak_reflections"),
    QuestDef("RC-02", "Recovery Quest", "recovery",
             "After a streak break, journal or learn on 2 distinct days "
             "(reviews, lessons or emotional entries - trades do not count).",
             1, config.XP_STREAK_RECOVERY, condition="streak_recoveries"),
]

QUESTS_BY_CODE = {q.code: q for q in QUEST_CATALOG}

_EVALUATORS = {
    "trades": _trades,
    "quick_reviews": _quick_reviews,
    "deep_reviews": _deep_reviews,
    "lessons": _lessons,
    "emotional_entries": lambda db: _count(db, EmotionalEntry),
    "daily_reviews": lambda db: _count(db, DailyReview),
    "weekly_reviews": lambda db: _count(db, WeeklyReview),
    "first_symbol_and_setup": _first_symbol_and_setup,
    "linked_emotional": _linked_emotional,
    "total_xp_100": _total_xp_count,
    "distinct_daily_days": _distinct_daily_review_days,
    "deep_lessons": _deep_lessons,
    "edits_after_7_days": _edits_after_7_days,
    "weekly_advice": _weekly_advice,
    "streak_reflections": _streak_reflections_done,
    "streak_recoveries": _streak_recoveries_done,
}


def is_consistency_enabled(db: Session) -> bool:
    row = db.query(UiPreference).filter(
        UiPreference.key == "consistency_quests_enabled").first()
    return bool(row and row.value == "true")


def quest_progress_row(db: Session, code: str) -> QuestProgress:
    row = db.query(QuestProgress).filter(QuestProgress.quest_code == code).first()
    if row is None:
        row = QuestProgress(quest_code=code, progress_current=0)
        db.add(row)
        db.flush()
    return row


def evaluate_quests(db: Session) -> None:
    """Recompute progress for all quests from persisted records.

    Completion is latched: once ``completed_at`` is set it is never cleared
    (deleted records can lower counters, but a completed quest stays
    completed - no punishment mechanics).
    """
    consistency_enabled = is_consistency_enabled(db)
    for q in QUEST_CATALOG:
        row = quest_progress_row(db, q.code)
        if q.status == "deferred":
            continue
        if q.opt_in and not consistency_enabled:
            continue  # opt-in quests stay untouched while disabled
        value = _EVALUATORS[q.condition](db)
        row.progress_current = min(value, q.target)
        if row.completed_at is None and row.progress_current >= q.target:
            row.completed_at = config.now_local()

def quest_state(db: Session, code: str) -> dict:
    """Serializable state for one quest (catalog + progress + claim)."""
    q = QUESTS_BY_CODE[code]
    row = quest_progress_row(db, code)
    claimed_at = row.claimed_at
    if q.code in config.PER_EVENT_QUEST_CODES:
        # Per-event quests: claimable while ANY event that earned the reward has
        # not claimed it yet, so a later independent streak break becomes
        # claimable again.  claimed_at reflects the most recent claim.
        from . import streaks as streaks_service

        pending = streaks_service.pending_claim_events(db, q.code)
        latest = streaks_service.latest_claim_time(db, q.code)
        if latest is not None:
            claimed_at = latest
        claimable = bool(
            q.status == "active"
            and row.completed_at is not None
            and q.reward_xp is not None
            and pending
        )
    else:
        claimable = bool(
            q.status == "active"
            and row.completed_at is not None
            and row.claimed_at is None
            and q.reward_xp is not None
        )
    return {
        "code": q.code,
        "name": q.name,
        "category": q.category,
        "description": q.description,
        "target": q.target,
        "progress_current": row.progress_current,
        "reward_xp": q.reward_xp,          # None => undecided (CN quests)
        "opt_in": q.opt_in,
        "status": q.status,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "claimed_at": claimed_at.isoformat() if claimed_at else None,
        "claimable": claimable,
    }


def all_quest_states(db: Session) -> list[dict]:
    return [quest_state(db, q.code) for q in QUEST_CATALOG]


def claim_quest(db: Session, code: str) -> dict:
    """Explicit claim workflow.

    Validates: quest exists and is active, is completed, has a decided reward,
    and was not claimed before.  The XP event (idempotency key
    ``quest:{CATALOG_VERSION}:{code}``) and the claim-state update happen in
    the caller's transaction, so a duplicate or concurrent claim can never
    double-award.  Raises KeyError / PermissionError with clear messages.

    RC-01 / RC-02 are **per-event** quests: they delegate to the streak service,
    which awards the reward once for every independent streak-break event using
    the ledger key ``streak:{event_id}:{code}``.  Every other quest keeps the
    original once-per-quest behaviour exactly as before.
    """
    q = QUESTS_BY_CODE.get(code)
    if q is None:
        raise KeyError(code)
    if q.status == "deferred":
        raise PermissionError(f"Quest {code} is deferred and cannot be claimed")
    if q.reward_xp is None:
        raise PermissionError(
            f"Quest {code} reward is undecided and cannot be claimed yet"
        )
    if code in config.PER_EVENT_QUEST_CODES:
        return _claim_per_event_quest(db, code)
    row = quest_progress_row(db, code)
    if row.completed_at is None:
        raise PermissionError(f"Quest {code} is not completed yet")
    if row.claimed_at is not None:
        raise PermissionError(f"Quest {code} was already claimed")
    pre_total = xp_service.total_xp(db)
    awarded = xp_service.award_quest_xp(db, quest_code=code, amount=q.reward_xp)
    row.claimed_at = config.now_local()
    feedback = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    return {
        "awarded_xp": awarded,
        "level_up": feedback["level_up"],
        "quest": quest_state(db, code),
    }


def _claim_per_event_quest(db: Session, code: str) -> dict:
    """Award RC-01 / RC-02 for every streak event that earned but not claimed."""
    from . import streaks as streaks_service

    pending = streaks_service.pending_claim_events(db, code)
    if not pending:
        raise PermissionError(
            f"Quest {code} has already been claimed for every streak break"
        )
    pre_total = xp_service.total_xp(db)
    result = streaks_service.claim_streak_quest(db, code)
    awarded = result["awarded_xp"]
    if awarded == 0:  # another request won the race for all pending events
        raise PermissionError(
            f"Quest {code} has already been claimed for every streak break"
        )
    row = quest_progress_row(db, code)   # keep the card's claimed_at meaningful
    if row.claimed_at is None:
        row.claimed_at = config.now_local()
    feedback = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    return {
        "awarded_xp": awarded,
        "level_up": feedback["level_up"],
        "quest": quest_state(db, code),
        "claimed_event_ids": result["event_ids"],
    }


