"""Serialization helpers: ORM trades -> JSON-ready row dicts with every
derived field attached."""
from __future__ import annotations

from typing import Any

from . import calculations as calc
from .models import Trade

#: The 25 user-editable Journal columns (Excel letters in comments).
TRADE_INPUT_FIELDS = [
    "symbol",              # B
    "opening_day",         # C
    "opening_time",        # D
    "setup_type",          # E
    "direction",           # F
    "volume",              # G
    "entry_price",         # H
    "sl_price",            # I
    "tp_price",            # K
    "risk",                # M
    "bias_4h",             # N
    "bias_1h",             # O
    "story_behind_candles",  # P
    "opening_rsi_condition",  # Q
    "atr",                 # R
    "mental_state",        # S
    "why_i_entered",       # T
    "closing_day",        # U
    "closing_time",       # V
    "closing_price",      # W
    "closing_rsi",        # X
    "why_i_closed",       # Y
    "commission",         # AA
    "swap",                # AB
    "note",                # AF
]

# Fields that may be sorted on (input + derived).
SORTABLE_FIELDS = set(TRADE_INPUT_FIELDS) | {
    "seq",
    "sl_atr_multiplier",
    "planned_rr",
    "final_rr",
    "net_pnl",
    "status",
    "duration_seconds",
    "win_streak",
    "loss_streak",
}


def trade_to_row(trade: Trade) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": trade.id,
        "seq": trade.seq,
        "source_net_pnl": trade.source_net_pnl,
    }
    for field in TRADE_INPUT_FIELDS:
        row[field] = getattr(trade, field)
    return row


def serialize_trades(trades: list[Trade]) -> list[dict[str, Any]]:
    """Convert ORM trades to full rows (input + derived + streaks)."""
    rows = [trade_to_row(t) for t in trades]
    for row in rows:
        row.update(calc.derive_trade(row))
    calc.attach_streaks(rows)
    return rows


def serialize_single(trades: list[Trade], trade_id: int) -> dict[str, Any] | None:
    for row in serialize_trades(trades):
        if row["id"] == trade_id:
            return row
    return None
