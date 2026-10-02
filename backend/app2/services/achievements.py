"""Achievement catalog and unlock evaluation.

Every condition below is based on verifiable persisted activity.  No
achievement depends on P&L, win rate, trade size, risk or trade frequency.
Unlock records (``achievement_unlocks``) are immutable once written; only
``seen_at`` may be updated afterwards.  Hidden achievements stay hidden
until unlocked.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config
from ..models import (
    AchievementUnlock,
    DailyReview,
    DeepReview,
    EmotionalEntry,
    Lesson,
    QuickReview,
    Setup,
    Symbol,
    Trade,
    WeeklyReview,
)


@dataclass(frozen=True)
class AchievementDef:
    code: str
    name: str
    category: str          # initiation | reflection | knowledge | curation | secret
    description: str
    hidden: bool = False


def _count(db: Session, model, *filters) -> int:
    q = db.query(func.coalesce(func.count(model.id), 0))
    for f in filters:
        q = q.filter(f)
    return int(q.scalar() or 0)


def _night_shift(db: Session) -> bool:
    """A trade opened between 00:00 and 05:00 local time."""
    trades = (
        db.query(Trade)
        .filter(Trade.deleted_at.is_(None), Trade.opened_at.isnot(None))
        .all()
    )
    for t in trades:
        opened = t.opened_at
        if hasattr(opened, "time") and opened.time().hour < 5:
            return True
    return False


def _phoenix(db: Session) -> bool:
    """A manually-closed 'loss' trade that received a complete Deep Review.

    'Complete' = every structured section answered.  Uses the explicit
    ``result`` field only - never P&L.
    """
    rows = (
        db.query(DeepReview)
        .join(Trade, Trade.id == DeepReview.trade_id)
        .filter(Trade.result == "loss", Trade.deleted_at.is_(None))
        .all()
    )
    for r in rows:
        if all(
            getattr(r, f) not in (None, "")
            for f in ("plan_review", "execution_review", "risk_review",
                      "emotions_review", "mistakes")
        ):
            return True
    return False

def _recovery_phoenix(db: Session) -> bool:
    """A streak break that was reflected on AND fully recovered from.

    Uses the same precedent as ``_phoenix`` (ACH-SECRET-PHOENIX): a purely
    verifiable, persisted state - never a trading outcome.  The unlock row is
    written once because ``achievement_unlocks.code`` is the primary key, so it
    can never be duplicated or re-awarded.
    """
    from . import streaks as streaks_service

    return bool(streaks_service.completed_reflection_count(db)) and bool(
        streaks_service.completed_recovery_count(db))


ACHIEVEMENT_CATALOG: list[AchievementDef] = [
    AchievementDef("ACH-INIT-TRADE", "First Steps", "initiation",
                   "Log your first trade."),
    AchievementDef("ACH-INIT-QR", "First Reflection", "initiation",
                   "Complete your first Quick Review."),
    AchievementDef("ACH-INIT-DR", "Deep Diver", "initiation",
                   "Complete your first Deep Review."),
    AchievementDef("ACH-INIT-EMO", "Heart on Sleeve", "initiation",
                   "Write your first Emotional Journal entry."),
    AchievementDef("ACH-INIT-DAILY", "Day One", "initiation",
                   "Complete your first Daily Review."),
    AchievementDef("ACH-INIT-WEEKLY", "Week One", "initiation",
                   "Complete your first Weekly Review."),
    AchievementDef("ACH-INIT-LESSON", "First Lesson", "initiation",
                   "Document your first lesson."),
    AchievementDef("ACH-REF-QUICK10", "Habit Forming", "reflection",
                   "Complete 10 Quick Reviews."),
    AchievementDef("ACH-REF-DEEP5", "The Autopsy Crew", "reflection",
                   "Complete 5 Deep Reviews."),
    AchievementDef("ACH-KNOW-LESSONS10", "Knowledge Seeker", "knowledge",
                   "Document 10 lessons."),
    AchievementDef("ACH-CUR-LISTS", "Cartographer", "curation",
                   "Create at least 5 symbols and 3 setups in Settings."),
    AchievementDef("ACH-SECRET-NIGHT", "Night Shift", "secret",
                   "Log a trade opened between 00:00 and 05:00.", hidden=True),
    AchievementDef("ACH-SECRET-PHOENIX", "The Phoenix", "secret",
                   "Give a manually-closed losing trade a complete Deep Review.",
                   hidden=True),
    AchievementDef("ACH-REC-PHOENIX", "Rising Phoenix", "secret",
                   "Reflect on a broken journaling streak, then build your "
                   "routine back up.", hidden=True),
]

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENT_CATALOG}


def _conditions_met(db: Session, code: str) -> bool:
    if code == "ACH-INIT-TRADE":
        return _count(db, Trade, Trade.deleted_at.is_(None)) >= 1
    if code == "ACH-INIT-QR":
        return _count(db, QuickReview) >= 1
    if code == "ACH-INIT-DR":
        return _count(db, DeepReview) >= 1
    if code == "ACH-INIT-EMO":
        return _count(db, EmotionalEntry) >= 1
    if code == "ACH-INIT-DAILY":
        return _count(db, DailyReview) >= 1
    if code == "ACH-INIT-WEEKLY":
        return _count(db, WeeklyReview) >= 1
    if code == "ACH-INIT-LESSON":
        return _count(db, Lesson) >= 1
    if code == "ACH-REF-QUICK10":
        return _count(db, QuickReview) >= 10
    if code == "ACH-REF-DEEP5":
        return _count(db, DeepReview) >= 5
    if code == "ACH-KNOW-LESSONS10":
        return _count(db, Lesson) >= 10
    if code == "ACH-CUR-LISTS":
        return _count(db, Symbol) >= 5 and _count(db, Setup) >= 3
    if code == "ACH-SECRET-NIGHT":
        return _night_shift(db)
    if code == "ACH-SECRET-PHOENIX":
        return _phoenix(db)
    if code == "ACH-REC-PHOENIX":
        return _recovery_phoenix(db)
    return False

def evaluate_achievements(db: Session) -> None:
    """Unlock any achievement whose condition is met.

    Idempotent: a code already present in ``achievement_unlocks`` is never
    re-inserted (duplicate unlock prevention).  Unlock history is immutable.
    """
    unlocked = {row[0] for row in db.query(AchievementUnlock.code).all()}
    for a in ACHIEVEMENT_CATALOG:
        if a.code in unlocked:
            continue
        if _conditions_met(db, a.code):
            db.add(AchievementUnlock(code=a.code, unlocked_at=config.now_local()))


def achievement_states(db: Session) -> list[dict]:
    """Serializable list; hidden achievements show as '???' until unlocked."""
    unlocked = {row.code: row for row in db.query(AchievementUnlock).all()}
    result = []
    for a in ACHIEVEMENT_CATALOG:
        row = unlocked.get(a.code)
        revealed = row is not None or not a.hidden
        result.append({
            "code": a.code,
            "name": a.name if revealed else "???",
            "category": a.category,
            "description": a.description if revealed else "Hidden achievement.",
            "hidden": a.hidden,
            "unlocked": row is not None,
            "unlocked_at": row.unlocked_at.isoformat() if row else None,
            "seen_at": row.seen_at.isoformat() if row and row.seen_at else None,
        })
    return result


