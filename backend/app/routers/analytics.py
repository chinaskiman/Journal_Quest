"""Analytics endpoint - live dashboard payload with optional filters."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..analytics import build_analytics
from ..db import get_db
from ..models import OptionValue
from ..serializers import serialize_trades
from .trades import _fetch_filtered

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def get_analytics(
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
    db: Session = Depends(get_db),
):
    trades = _fetch_filtered(
        db,
        search=search, symbol=symbol, direction=direction, setup_type=setup_type,
        bias_4h=bias_4h, bias_1h=bias_1h, mental_state=mental_state,
        rsi_condition=rsi_condition, opening_from=opening_from, opening_to=opening_to,
        closing_from=closing_from, closing_to=closing_to,
    )
    rows = serialize_trades(trades)
    if status:
        rows = [r for r in rows if r.get("status") == status]

    option_lists: dict[str, list[str]] = {}
    for option in (
        db.query(OptionValue)
        .order_by(OptionValue.list_key, OptionValue.position, OptionValue.id)
    ):
        option_lists.setdefault(option.list_key, []).append(option.value)

    return build_analytics(rows, option_lists)
