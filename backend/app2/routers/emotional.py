"""Emotional Journal endpoints.

Approved XP rule (exact):
* First entry on a LOCAL calendar day: +10 XP, key ``emotional:{local_date}``
  (deterministic daily key - app restarts and retries cannot duplicate it;
  the UNIQUE constraint makes concurrent double-bonuses impossible).
* Every additional entry the same day: +2 XP, key
  ``emotional-entry:{entry_id}`` (unique per entry).
* Edits award nothing; deletes never claw back XP.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import EmotionalEntry, Emotion, Trade
from ..schemas import (
    EmotionalEntryCreate,
    EmotionalEntryMutationOut,
    EmotionalEntryOut,
    EmotionalEntryUpdate,
    EmotionalListOut,
)
from ..services import xp as xp_service
from ..services.activity import run_progress_engine

router = APIRouter(prefix="/api/emotional-entries", tags=["emotional"])


def _get_entry(db: Session, entry_id: int) -> EmotionalEntry:
    row = db.get(EmotionalEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return row


def _validate_emotion(db: Session, emotion: str | None) -> None:
    if emotion is None:
        return
    exists = db.query(Emotion).filter(
        Emotion.name == emotion, Emotion.is_active == 1).first()
    if not exists:
        raise HTTPException(
            status_code=422,
            detail=f"Emotion '{emotion}' is not in Settings. "
                   "Create it first under Settings -> Emotions.",
        )


def _award_emotional_xp(db: Session, entry: EmotionalEntry) -> int:
    """Returns the amount actually awarded for this entry (10 or 2)."""
    day_key = f"emotional:{entry.local_date.isoformat()}"
    if not xp_service.has_event(db, day_key):
        return xp_service.award_xp(
            db,
            event_type="emotional_first",
            amount=config.XP_EMOTIONAL_FIRST_OF_DAY,
            idempotency_key=day_key,
            entity_type="emotional_entry",
            entity_id=entry.id,
            details={"local_date": entry.local_date.isoformat()},
        )
    return xp_service.award_xp(
        db,
        event_type="emotional_additional",
        amount=config.XP_EMOTIONAL_ADDITIONAL,
        idempotency_key=f"emotional-entry:{entry.id}",
        entity_type="emotional_entry",
        entity_id=entry.id,
        details={"local_date": entry.local_date.isoformat()},
    )


@router.get("", response_model=EmotionalListOut)
def list_entries(
    trade_id: int | None = None,
    local_date: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(EmotionalEntry)
    if trade_id is not None:
        q = q.filter(EmotionalEntry.trade_id == trade_id)
    if local_date:
        q = q.filter(EmotionalEntry.local_date == local_date)
    total = q.count()
    rows = (
        q.order_by(EmotionalEntry.occurred_at.desc(), EmotionalEntry.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return EmotionalListOut(
        rows=[EmotionalEntryOut.model_validate(r) for r in rows], total=total
    )

@router.post("", response_model=EmotionalEntryMutationOut, status_code=201)
def create_entry(payload: EmotionalEntryCreate,
                 db: Session = Depends(get_db)) -> EmotionalEntryMutationOut:
    _validate_emotion(db, payload.emotion)
    if payload.trade_id is not None:
        trade = db.get(Trade, payload.trade_id)
        if trade is None or trade.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Trade not found")
    pre_total = xp_service.total_xp(db)
    occurred = payload.occurred_at or config.now_local()
    # local_date is computed SERVER-SIDE from the local timezone - clients
    # never control day grouping.
    if occurred.tzinfo is not None:
        occurred_local = occurred.astimezone()
        stored = occurred.astimezone().replace(tzinfo=None)
    else:
        occurred_local = occurred.replace(tzinfo=config.now_local().tzinfo)
        stored = occurred
    entry = EmotionalEntry(
        trade_id=payload.trade_id,
        occurred_at=stored,
        local_date=occurred_local.date(),
        emotion_label=payload.emotion,
        intensity=payload.intensity,
        trigger=payload.trigger,
        body=payload.body,
    )
    db.add(entry)
    db.flush()
    awarded = _award_emotional_xp(db, entry)
    run_progress_engine(db)
    db.commit()
    db.refresh(entry)
    out = EmotionalEntryMutationOut.model_validate(entry)
    fb = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    out.xp_awarded = fb["xp_awarded"]
    out.level_up = fb["level_up"]
    return out


@router.get("/{entry_id}", response_model=EmotionalEntryOut)
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    return EmotionalEntryOut.model_validate(_get_entry(db, entry_id))


@router.patch("/{entry_id}", response_model=EmotionalEntryOut)
def update_entry(entry_id: int, payload: EmotionalEntryUpdate,
                 db: Session = Depends(get_db)):
    row = _get_entry(db, entry_id)
    data = payload.model_dump(exclude_unset=True)
    if "emotion" in data and data["emotion"] is not None:
        _validate_emotion(db, data["emotion"])
        row.emotion_label = data["emotion"]
    if "occurred_at" in data and data["occurred_at"] is not None:
        occurred = data["occurred_at"]
        if occurred.tzinfo is not None:
            row.occurred_at = occurred.astimezone().replace(tzinfo=None)
        else:
            row.occurred_at = occurred
        # NOTE: local_date is intentionally NOT recomputed on edit - the day
        # the XP was earned for stays in the ledger (append-only, no clawback).
    for field in ("intensity", "trigger", "body", "trade_id"):
        if field in data:
            setattr(row, field, data[field])
    db.commit()  # edits award ZERO XP
    db.refresh(row)
    return EmotionalEntryOut.model_validate(row)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    row = _get_entry(db, entry_id)
    db.delete(row)
    db.commit()  # no XP clawback - ledger is append-only
    return None

