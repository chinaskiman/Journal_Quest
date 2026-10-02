"""Options CRUD - the five dropdown lists of the workbook's Options sheet."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import OptionValue
from ..schemas import OptionCreate, OptionOut, OptionReorderPayload, OptionsOut, OptionUpdate
from ..validation import OPTION_LIST_KEYS

router = APIRouter(prefix="/api/options", tags=["options"])

LIST_LABELS = {
    "symbol": "Symbols",
    "setup_type": "Types",
    "bias": "Bias",
    "rsi_condition": "RSI Conditions",
    "mental_state": "Mental State",
}


def _get_list(list_key: str) -> str:
    if list_key not in OPTION_LIST_KEYS:
        raise HTTPException(404, f"Unknown option list '{list_key}'")
    return list_key


def _ordered(db: Session, list_key: str):
    return (
        db.query(OptionValue)
        .filter(OptionValue.list_key == list_key)
        .order_by(OptionValue.position, OptionValue.id)
        .all()
    )


@router.get("", response_model=OptionsOut)
def get_options(db: Session = Depends(get_db)):
    lists: dict[str, list[OptionOut]] = {key: [] for key in OPTION_LIST_KEYS}
    for option in db.query(OptionValue).order_by(
        OptionValue.list_key, OptionValue.position, OptionValue.id
    ):
        lists.setdefault(option.list_key, []).append(
            OptionOut.model_validate(option, from_attributes=True)
        )
    return OptionsOut(lists=lists)


@router.post("/{list_key}", response_model=OptionOut, status_code=201)
def add_option(list_key: str, payload: OptionCreate, db: Session = Depends(get_db)):
    _get_list(list_key)
    value = payload.value.strip() if payload.value else ""
    if not value:
        raise HTTPException(422, "Value must not be empty")
    exists = (
        db.query(OptionValue)
        .filter(OptionValue.list_key == list_key, OptionValue.value == value)
        .first()
    )
    if exists:
        raise HTTPException(409, f"'{value}' already exists in this list")
    position = (
        db.query(func.max(OptionValue.position))
        .filter(OptionValue.list_key == list_key)
        .scalar()
        or 0
    ) + 1
    option = OptionValue(list_key=list_key, value=value, position=position)
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


@router.patch("/{list_key}/{option_id}", response_model=OptionOut)
def update_option(
    list_key: str, option_id: int, payload: OptionUpdate, db: Session = Depends(get_db)
):
    _get_list(list_key)
    option = db.get(OptionValue, option_id)
    if option is None or option.list_key != list_key:
        raise HTTPException(404, f"Option {option_id} not found in '{list_key}'")
    value = payload.value.strip() if payload.value else ""
    if not value:
        raise HTTPException(422, "Value must not be empty")
    clash = (
        db.query(OptionValue)
        .filter(
            OptionValue.list_key == list_key,
            OptionValue.value == value,
            OptionValue.id != option_id,
        )
        .first()
    )
    if clash:
        raise HTTPException(409, f"'{value}' already exists in this list")
    option.value = value
    db.commit()
    db.refresh(option)
    return option


@router.delete("/{list_key}/{option_id}", status_code=204)
def delete_option(list_key: str, option_id: int, db: Session = Depends(get_db)):
    _get_list(list_key)
    option = db.get(OptionValue, option_id)
    if option is None or option.list_key != list_key:
        raise HTTPException(404, f"Option {option_id} not found in '{list_key}'")
    db.delete(option)
    db.commit()


@router.post("/{list_key}/reorder")
def reorder_options(
    list_key: str, payload: OptionReorderPayload, db: Session = Depends(get_db)
):
    _get_list(list_key)
    options = _ordered(db, list_key)
    by_id = {o.id: o for o in options}
    if set(payload.ordered_ids) != set(by_id) or len(payload.ordered_ids) != len(options):
        raise HTTPException(400, "ordered_ids must contain every option exactly once")
    for position, option_id in enumerate(payload.ordered_ids, start=1):
        by_id[option_id].position = position
    db.commit()
    return {"ok": True, "count": len(options)}
