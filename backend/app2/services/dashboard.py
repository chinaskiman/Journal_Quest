"""Dashboard aggregation - derived only from persisted records.

No fabricated counters: an empty database yields honest zero/empty values.
No metric depends on P&L or trading outcomes; the optional P&L summary only
*echoes* manually entered values (sum/count) and never influences
progression.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config
from ..models import (
    AchievementUnlock,
    DailyReview,
    DeepReview,
    EmotionalEntry,
    Lesson,
    QuestProgress,
    QuickReview,
    Trade,
    WeeklyReview,
    XpEvent,
)
from . import levels as levels_service
from . import xp as xp_service
from . import quests as quests_service
from . import streaks as streaks_service


def _count(db: Session, model, *filters) -> int:
    q = db.query(func.coalesce(func.count(model.id), 0))
    for f in filters:
        q = q.filter(f)
    return int(q.scalar() or 0)


def dashboard_summary(db: Session) -> dict:
    total = xp_service.total_xp(db)
    info = levels_service.level_info(total)

    quests = quests_service.all_quest_states(db)
    completed = [q for q in quests if q["completed_at"]]
    claimable = [q for q in quests if q["claimable"]]
    claimed = [q for q in quests if q["claimed_at"]]

    trades_total = _count(db, Trade, Trade.deleted_at.is_(None))
    open_trades = _count(
        db, Trade, Trade.deleted_at.is_(None), Trade.status == "open"
    )
    # trades without any review (reflection nudge data)
    reviewed_trade_ids = {r[0] for r in db.query(QuickReview.trade_id).all()}
    reviewed_trade_ids |= {r[0] for r in db.query(DeepReview.trade_id).all()}
    unreviewed = _count(
        db, Trade, Trade.deleted_at.is_(None), Trade.status == "closed"
    )
    unreviewed_trades = [
        t.id for t in db.query(Trade)
        .filter(Trade.deleted_at.is_(None), Trade.status == "closed").all()
        if t.id not in reviewed_trade_ids
    ]

    today = config.today_local()
    today_daily = (
        db.query(DailyReview).filter(DailyReview.review_date == today).first()
    )
    iso_year, iso_week = config.iso_week_local(today)
    today_weekly = (
        db.query(WeeklyReview)
        .filter(WeeklyReview.iso_year == iso_year, WeeklyReview.iso_week == iso_week)
        .first()
    )

    recent_xp = (
        db.query(XpEvent).order_by(XpEvent.id.desc()).limit(20).all()
    )
    activity = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "amount": e.amount,
            "awarded_at": e.awarded_at.isoformat() if e.awarded_at else None,
        }
        for e in reversed(recent_xp)
    ]

    achievements_unlocked = db.query(AchievementUnlock).count()

    # Optional manual P&L echo (explicitly NOT used for any progression):
    pnl_count = _count(db, Trade, Trade.deleted_at.is_(None),
                        Trade.user_pnl.isnot(None))
    pnl_sum = db.query(
        func.coalesce(func.sum(Trade.user_pnl), 0)
    ).filter(Trade.deleted_at.is_(None), Trade.user_pnl.isnot(None)).scalar()

    return {
        "pilot": {
            "total_xp": total,
            "level": info.level,
            "title": info.title,
            "current_level_xp": info.current_level_xp,
            "next_level_xp_needed": info.next_level_xp_needed,
            "next_level_total_xp": info.next_level_total_xp,
            "progress_pct": info.progress_pct,
        },
        "quests": {
            "active": [q for q in quests
                       if not q["completed_at"] and q["status"] == "active"],
            "completed_count": len(completed),
            "claimable_count": len(claimable),
            "claimed_count": len(claimed),
        },
        "achievements": {"unlocked_count": achievements_unlocked},
        "journal": {
            "trades_total": trades_total,
            "open_trades": open_trades,
            "closed_trades": trades_total - open_trades,
            "unreviewed_trade_ids": unreviewed_trades,
            "quick_reviews": _count(db, QuickReview),
            "lessons": _count(db, Lesson),
            "emotional_entries": _count(db, EmotionalEntry),
            "daily_reviews": _count(db, DailyReview),
            "daily_review_done_today": today_daily is not None,
            "weekly_review_done_this_week": today_weekly is not None,
        },
        "manual_pnl_summary": {  # informational echo only
            "entries": pnl_count,
            "sum": float(pnl_sum or 0),
        },
        # Streak Break & Recovery.  Detection is idempotent and runs from the
        # progress engine; this only reports persisted state.  Streak days award
        # no XP, and a break never deducts anything.
        "streak": streaks_service.state(db),
        "recent_activity": activity,
    }
