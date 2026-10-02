"""Gamification read endpoints: XP, levels, quests, achievements.

All of these are read-only (except the explicit quest CLAIM action and the
achievement "seen" marker).  XP amounts and rewards are decided server-side
only; there is no endpoint that accepts an XP amount from a client.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import AchievementUnlock, StreakEvent, XpEvent
from ..schemas import StreakReflectionIn, XpEventOut, XpSummaryOut
from ..services import achievements as achievements_service
from ..services import levels as levels_service
from ..services import quests as quests_service
from ..services import streaks as streaks_service
from ..services import xp as xp_service
from ..services.activity import run_progress_engine

router = APIRouter(prefix="/api", tags=["gamification"])


@router.get("/xp", response_model=XpSummaryOut)
def get_xp_summary(db: Session = Depends(get_db)):
    info = levels_service.level_info(xp_service.total_xp(db))
    return XpSummaryOut(**info.__dict__)


@router.get("/xp/events")
def list_xp_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(XpEvent).order_by(XpEvent.id.desc())
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "rows": [XpEventOut.model_validate(r) for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/levels")
def get_levels():
    """Approved thresholds and titles (static reference for the frontend)."""
    return {
        "formula": "xp_to_advance(n) = 100 + 50 * (n - 1)",
        "titles": {str(k): v for k, v in levels_service.LEVEL_TITLES.items()},
        "mastery_title": levels_service.MASTERY_TITLE,
        "thresholds": [
            {"level": lvl, "cumulative_xp": levels_service.cumulative_threshold(lvl)}
            for lvl in range(1, 16)
        ],
    }


# --- quests -------------------------------------------------------------------

@router.get("/quests")
def list_quests(db: Session = Depends(get_db)):
    run_progress_engine(db)  # re-evaluate from persisted activity, then read
    db.commit()
    return {"items": quests_service.all_quest_states(db)}


@router.get("/quests/{quest_code}")
def get_quest(quest_code: str, db: Session = Depends(get_db)):
    run_progress_engine(db)
    db.commit()
    if quest_code not in quests_service.QUESTS_BY_CODE:
        raise HTTPException(status_code=404, detail="Unknown quest code")
    return quests_service.quest_state(db, quest_code)


@router.post("/quests/{quest_code}/claim")
def claim_quest(quest_code: str, db: Session = Depends(get_db)):
    """Explicit Claim action.  The reward amount is server-determined."""
    run_progress_engine(db)
    try:
        result = quests_service.claim_quest(db, quest_code)
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Unknown quest code")
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return result


# --- achievements ----------------------------------------------------------------

@router.get("/achievements")
def list_achievements(db: Session = Depends(get_db)):
    # Full progress engine (streak detection -> recovery -> quests ->
    # achievements) so the recovery badge reflects current persisted state
    # without the client having to visit the Quest Hub first.
    run_progress_engine(db)
    db.commit()
    return {"items": achievements_service.achievement_states(db)}


@router.post("/achievements/{code}/seen", status_code=204)
def mark_achievement_seen(code: str, db: Session = Depends(get_db)):
    row = db.get(AchievementUnlock, code)
    if row is None:
        raise HTTPException(status_code=404, detail="Achievement not unlocked")
    row.seen_at = config.now_local()
    db.commit()  # only seen_at is mutable - unlock history is immutable
    return None


# --- streak break & recovery ----------------------------------------------------
def _active_streak_event(db: Session) -> StreakEvent:
    """Resolve the event a streak write applies to, or fail clearly."""
    event = streaks_service.latest_event(db)
    if event is None:
        raise HTTPException(
            status_code=404,
            detail="No streak break recorded yet. Streak events are created "
                   "only after an eligible break is detected.")
    return event


@router.get("/streak")
def get_streak(db: Session = Depends(get_db)):
    """Current streak, tracking state and the newest recovery lifecycle.

    Read-only: it never creates a break by itself (detection runs inside the
    normal progress engine) and it can be called as often as the UI likes.
    """
    return streaks_service.state(db)


@router.post("/streak/alert-seen")
def mark_streak_alert_seen(db: Session = Depends(get_db)):
    """Dismiss the Quest Hub alert for the current event (idempotent)."""
    event = _active_streak_event(db)
    streaks_service.mark_alert_seen(db, event)
    db.commit()
    return streaks_service.event_progress(db, event)


@router.put("/streak/reflection")
def save_streak_reflection(
    payload: StreakReflectionIn, db: Session = Depends(get_db)
):
    """Create-or-update the single reflection for the current streak event.

    Idempotent: the reflection is unique per event, so repeated submissions
    update one row and can never award XP twice.  XP is granted only through the
    explicit, idempotent RC-01 claim.
    """
    event = _active_streak_event(db)
    result = streaks_service.save_reflection(
        db, event,
        obstacle=(payload.obstacle or "").strip() or None,
        resume_step=(payload.resume_step or "").strip() or None,
    )
    # re-evaluate so RC-01 / the recovery achievement see the new state
    run_progress_engine(db)
    db.commit()
    return result
