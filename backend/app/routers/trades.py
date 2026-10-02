"""Journal CRUD + list filtering/sorting/pagination."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Trade
from ..schemas import ReorderPayload, TradeCreate, TradeListOut, TradeOut, TradeUpdate
from ..serializers import SORTABLE_FIELDS, TRADE_INPUT_FIELDS, serialize_single, serialize_trades
from ..validation import validate_trade_payload

router = APIRouter(prefix="/api/trades", tags=["trades"])


def _fetch_filtered(
    db: Session,
    *,
    search: str | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    setup_type: str | None = None,
    bias_4h: str | None = None,
    bias_1h: str | None = None,
    mental_state: str | None = None,
    rsi_condition: str | None = None,
    opening_from: dt.date | None = None,
    opening_to: dt.date | None = None,
    closing_from: dt.date | None = None,
    closing_to: dt.date | None = None,
) -> list[Trade]:
    query = db.query(Trade)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Trade.symbol.ilike(like),
                Trade.setup_type.ilike(like),
                Trade.mental_state.ilike(like),
                Trade.story_behind_candles.ilike(like),
                Trade.opening_rsi_condition.ilike(like),
                Trade.why_i_entered.ilike(like),
                Trade.why_i_closed.ilike(like),
                Trade.note.ilike(like),
            )
        )
    for column, value in (
        (Trade.symbol, symbol),
        (Trade.direction, direction),
        (Trade.setup_type, setup_type),
        (Trade.bias_4h, bias_4h),
        (Trade.bias_1h, bias_1h),
        (Trade.mental_state, mental_state),
    ):
        if value:
            query = query.filter(column == value)
    if rsi_condition:
        query = query.filter(Trade.opening_rsi_condition.ilike(f"%{rsi_condition}%"))
    if opening_from:
        query = query.filter(Trade.opening_day >= opening_from)
    if opening_to:
        query = query.filter(Trade.opening_day <= opening_to)
    if closing_from:
        query = query.filter(Trade.closing_day >= closing_from)
    if closing_to:
        query = query.filter(Trade.closing_day <= closing_to)

    return query.all()


def _python_filter(rows: list[dict], status: str | None) -> list[dict]:
    if not status:
        return rows
    return [r for r in rows if r.get("status") == status]


def _sort_rows(rows: list[dict], key: str, desc: bool) -> list[dict]:
    """Sort with NULLs always last, regardless of direction."""
    present = [r for r in rows if r.get(key) is not None]
    missing = [r for r in rows if r.get(key) is None]

    def value(r: dict):
        v = r.get(key)
        return v.lower() if isinstance(v, str) else v

    present.sort(key=value, reverse=desc)
    return present + missing


@router.get("", response_model=TradeListOut)
def list_trades(
    search: str | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    setup_type: str | None = None,
    bias_4h: str | None = None,
    bias_1h: str | None = None,
    mental_state: str | None = None,
    status: str | None = None,
    rsi_condition: str | None = None,
    opening_from: dt.date | None = None,
    opening_to: dt.date | None = None,
    closing_from: dt.date | None = None,
    closing_to: dt.date | None = None,
    sort: str = Query(default="seq"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5000, ge=0, le=5000),
    db: Session = Depends(get_db),
):
    if sort not in SORTABLE_FIELDS:
        raise HTTPException(422, f"Cannot sort by '{sort}'")
    trades = _fetch_filtered(
        db,
        search=search, symbol=symbol, direction=direction, setup_type=setup_type,
        bias_4h=bias_4h, bias_1h=bias_1h, mental_state=mental_state,
        rsi_condition=rsi_condition, opening_from=opening_from, opening_to=opening_to,
        closing_from=closing_from, closing_to=closing_to,
    )
    rows = _python_filter(serialize_trades(trades), status)
    rows = _sort_rows(rows, sort, order == "desc")

    total = len(rows)
    if page_size == 0:  # 0 = return everything
        return TradeListOut(rows=rows, total=total, page=1, page_size=total)
    start = (page - 1) * page_size
    return TradeListOut(
        rows=rows[start : start + page_size], total=total, page=page, page_size=page_size
    )


def _next_seq(db: Session) -> int:
    return (db.query(func.max(Trade.seq)).scalar() or 0) + 1


def _renumber(db: Session) -> None:
    """Compact seq values to 1..N preserving current order (like Excel's
    row numbers when a row is deleted)."""
    trades = db.query(Trade).order_by(Trade.seq, Trade.id).all()
    offset = len(trades) + max((t.seq for t in trades), default=0) + 1
    for i, trade in enumerate(trades):
        trade.seq = offset + i
    db.flush()
    for i, trade in enumerate(trades):
        trade.seq = i + 1
    db.flush()


@router.post("", response_model=TradeOut, status_code=201)
def create_trade(payload: TradeCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    validate_trade_payload(db, data, None)
    trade = Trade(**{f: data[f] for f in TRADE_INPUT_FIELDS}, seq=_next_seq(db))
    db.add(trade)
    db.commit()
    return serialize_single(db.query(Trade).all(), trade.id)


@router.get("/{trade_id}", response_model=TradeOut)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(404, f"Trade {trade_id} not found")
    return serialize_single(db.query(Trade).all(), trade_id)


@router.patch("/{trade_id}", response_model=TradeOut)
def update_trade(trade_id: int, payload: TradeUpdate, db: Session = Depends(get_db)):
    trade = db.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(404, f"Trade {trade_id} not found")
    data = payload.model_dump(exclude_unset=True)
    validate_trade_payload(db, data, trade)
    for field, value in data.items():
        setattr(trade, field, value)
    db.commit()
    return serialize_single(db.query(Trade).all(), trade_id)


@router.delete("/{trade_id}", status_code=204)
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(404, f"Trade {trade_id} not found")
    db.delete(trade)
    db.commit()
    _renumber(db)
    db.commit()


@router.post("/{trade_id}/duplicate", response_model=TradeOut, status_code=201)
def duplicate_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(404, f"Trade {trade_id} not found")
    clone = Trade(
        seq=_next_seq(db),
        **{f: getattr(trade, f) for f in TRADE_INPUT_FIELDS},
    )
    db.add(clone)
    db.commit()
    return serialize_single(db.query(Trade).all(), clone.id)


@router.post("/reorder")
def reorder_trades(payload: ReorderPayload, db: Session = Depends(get_db)):
    trades = db.query(Trade).all()
    if set(payload.ordered_ids) != {t.id for t in trades} or len(
        payload.ordered_ids
    ) != len(trades):
        raise HTTPException(400, "ordered_ids must contain every trade exactly once")
    by_id = {t.id: t for t in trades}
    offset = len(trades) + max(t.seq for t in trades) + 1
    for i, trade_id in enumerate(payload.ordered_ids):
        by_id[trade_id].seq = offset + i
    db.flush()
    for i, trade_id in enumerate(payload.ordered_ids):
        by_id[trade_id].seq = i + 1
    db.commit()
    return {"ok": True, "count": len(trades)}
