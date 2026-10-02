"""XP ledger service - the ONLY way XP enters the system.

Rules enforced here (approved, see PHASE1_BLUEPRINT.md and the Phase 2 spec):

* XP amounts always come from server-side configuration - a client can never
  supply or override an amount.
* Every event carries a UNIQUE idempotency key; a duplicate key means the
  activity already earned its XP and no second event is inserted.
* ``award_xp`` must be called inside the caller's transaction so the activity
  record and its XP event commit atomically (or roll back together).
* The ledger is append-only; edits and deletions never touch it (no clawback).
"""
from __future__ import annotations

import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config
from sqlalchemy.exc import IntegrityError

from ..models import XpEvent


# Approved XP values (single source of truth: config.py constants).
XP_VALUES = {
    "trade_create": config.XP_TRADE_CREATE,
    "quick_review": config.XP_QUICK_REVIEW,
    "deep_review": config.XP_DEEP_REVIEW,
    "lesson": config.XP_LESSON,
    "emotional_first": config.XP_EMOTIONAL_FIRST_OF_DAY,
    "emotional_additional": config.XP_EMOTIONAL_ADDITIONAL,
    "daily_review": config.XP_DAILY_REVIEW,
    "weekly_review": config.XP_WEEKLY_REVIEW,
}


def total_xp(db: Session) -> int:
    """Total XP derived from the persisted ledger (never trusted from clients)."""
    value = db.query(func.coalesce(func.sum(XpEvent.amount), 0)).scalar()
    return int(value or 0)


def has_event(db: Session, idempotency_key: str) -> bool:
    return (
        db.query(XpEvent.id)
        .filter(XpEvent.idempotency_key == idempotency_key)
        .first()
        is not None
    )


def award_xp(
    db: Session,
    *,
    event_type: str,
    amount: int,
    idempotency_key: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
) -> int:
    """Insert an XP event if (and only if) the idempotency key is unused.

    Returns the amount actually awarded (0 when the key already exists).
    Must be called inside the caller's transaction - if the surrounding
    transaction rolls back, the XP event rolls back with it.
    """
    if has_event(db, idempotency_key):
        return 0
    event = XpEvent(
        event_type=event_type,
        amount=int(amount),
        idempotency_key=idempotency_key,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        # Concurrent duplicate: the UNIQUE constraint is the hard backstop.
        db.rollback()
        raise
    return int(amount)


def award_quest_xp(
    db: Session,
    *,
    quest_code: str,
    amount: int,
) -> int:
    """Quest rewards use a version-tolerant key: quest:{catalog_version}:{code}."""
    from .quests import CATALOG_VERSION
    return award_xp(
        db,
        event_type="quest",
        amount=amount,
        idempotency_key=f"quest:{CATALOG_VERSION}:{quest_code}",
        entity_type="quest",
        details={"quest_code": quest_code},
    )


def streak_quest_key(event_id: int, quest_code: str) -> str:
    """Per-event quest reward key: streak:{event_id}:{quest_code}.

    Distinct from the global ``quest:{version}:{code}`` key so an independent
    later streak break can earn RC-01 / RC-02 again, while the same event can
    never earn it twice (the ledger's UNIQUE idempotency key is the firewall).
    """
    return f"streak:{event_id}:{quest_code}"


def award_streak_quest_xp(
    db: Session,
    *,
    event_id: int,
    quest_code: str,
    amount: int,
) -> int:
    """RC-01 / RC-02 reward for ONE streak-break event, through the normal ledger."""
    return award_xp(
        db,
        event_type="quest",
        amount=amount,
        idempotency_key=streak_quest_key(event_id, quest_code),
        entity_type="quest",
        entity_id=event_id,
        details={"quest_code": quest_code, "streak_event_id": event_id},
    )


def mutation_feedback(
    db: Session, *, pre_total_xp: int, xp_awarded: int
) -> dict:
    """Feedback payload for mutation responses (frontend integration).

    ``pre_total_xp`` is the ledger total read *before* the mutation's award;
    ``xp_awarded`` is what ``award_xp`` actually inserted for this operation.
    ``level_up`` is non-null only when this mutation crossed a level
    threshold - levels are always derived from the ledger, never computed
    a second time by the client, and no extra XP is inserted here.
    """
    from .levels import level_from_xp, title_for_level

    if xp_awarded <= 0:
        return {"xp_awarded": 0, "level_up": None}
    post_level = level_from_xp(total_xp(db))
    pre_level = level_from_xp(pre_total_xp)
    level_up = (
        {"level": post_level, "title": title_for_level(post_level)}
        if post_level > pre_level else None
    )
    return {"xp_awarded": xp_awarded, "level_up": level_up}
