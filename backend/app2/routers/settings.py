"""Settings CRUD - symbols, setups, emotions, UI preferences.

Historical-label preservation strategy:
* Journal records store *label snapshots* (e.g. ``trades.symbol_label``), so
  renaming a settings row never rewrites history.
* DELETE is soft by default (``is_active=0``): the value disappears from
  active dropdowns but remains distinguishable in the table and in history.
* Hard delete (``?hard=true``) is refused while any journal record still
  references the label - historical data can never be orphaned.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Emotion, EmotionalEntry, Setup, Symbol, Trade, UiPreference
from ..schemas import (
    SettingCreate,
    SettingListOut,
    SettingOut,
    SettingUpdate,
    UiPreferenceUpdate,
)
from ..services.activity import run_progress_engine

router = APIRouter(prefix="/api/settings", tags=["settings"])

_LISTS = {"symbols": Symbol, "setups": Setup, "emotions": Emotion}


def _model(list_name: str):
    model = _LISTS.get(list_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown settings list '{list_name}'")
    return model


def _referenced(db: Session, model, name: str) -> int:
    if model is Symbol:
        return db.query(Trade).filter(
            Trade.symbol_label == name, Trade.deleted_at.is_(None)
        ).count()
    if model is Setup:
        return db.query(Trade).filter(
            Trade.setup_label == name, Trade.deleted_at.is_(None)
        ).count()
    return db.query(EmotionalEntry).filter(EmotionalEntry.emotion_label == name).count()


@router.get("/{list_name}", response_model=SettingListOut)
def list_settings(list_name: str, db: Session = Depends(get_db),
                  include_inactive: bool = False):
    model = _model(list_name)
    q = db.query(model)
    if not include_inactive:
        q = q.filter(model.is_active == 1)
    rows = q.order_by(model.sort_order, model.id).all()
    return SettingListOut(items=[SettingOut.model_validate(r) for r in rows])


@router.post("/{list_name}", response_model=SettingOut, status_code=201)
def create_setting(list_name: str, payload: SettingCreate,
                   db: Session = Depends(get_db)):
    model = _model(list_name)
    if db.query(model).filter(model.name == payload.name).first():
        raise HTTPException(status_code=409, detail=f"'{payload.name}' already exists")
    max_order = db.query(model.sort_order).order_by(model.sort_order.desc()).first()
    row = model(
        name=payload.name,
        sort_order=(max_order[0] + 1) if max_order else 1,
        is_active=True,
    )
    db.add(row)
    # FT-07 / curation achievements react to new settings rows
    run_progress_engine(db)
    db.commit()
    db.refresh(row)
    return SettingOut.model_validate(row)

@router.patch("/{list_name}/{item_id}", response_model=SettingOut)
def update_setting(list_name: str, item_id: int, payload: SettingUpdate,
                   db: Session = Depends(get_db)):
    model = _model(list_name)
    row = db.get(model, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    if payload.name is not None and payload.name != row.name:
        if db.query(model).filter(model.name == payload.name).first():
            raise HTTPException(status_code=409, detail=f"'{payload.name}' already exists")
        row.name = payload.name
        # Historical records keep the old snapshot label - intentional.
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    db.commit()
    db.refresh(row)
    return SettingOut.model_validate(row)


@router.delete("/{list_name}/{item_id}", status_code=204)
def delete_setting(list_name: str, item_id: int,
                   hard: bool = Query(False, description=(
                       "Hard delete. Refused while journal records still "
                       "reference the label.")),
                   db: Session = Depends(get_db)):
    model = _model(list_name)
    row = db.get(model, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    if hard:
        refs = _referenced(db, model, row.name)
        if refs:
            raise HTTPException(
                status_code=409,
                detail=(f"Cannot hard delete '{row.name}': {refs} journal "
                        "record(s) reference this label. Use the soft delete "
                        "(default) to keep history intact."),
            )
        db.delete(row)
    else:
        row.is_active = False  # soft: archived, history preserved
    db.commit()
    return None


# --- UI preferences -----------------------------------------------------------

preferences_router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@preferences_router.get("")
def get_preferences(db: Session = Depends(get_db)):
    rows = db.query(UiPreference).all()
    out: dict[str, object] = {}
    for row in rows:
        try:
            out[row.key] = json.loads(row.value)
        except (TypeError, ValueError):
            out[row.key] = row.value
    return {"items": out}


@preferences_router.put("/{key}")
def put_preference(key: str, payload: UiPreferenceUpdate,
                   db: Session = Depends(get_db)):
    # validate JSON-ness before storing
    try:
        json.loads(payload.value)
    except ValueError:
        raise HTTPException(status_code=422, detail="value must be valid JSON")
    row = db.query(UiPreference).filter(UiPreference.key == key).first()
    if row is None:
        row = UiPreference(key=key, value=payload.value)
        db.add(row)
    else:
        row.value = payload.value
    # opt-in consistency quests listen to this key
    run_progress_engine(db)
    db.commit()
    return {"key": key, "stored": True}

