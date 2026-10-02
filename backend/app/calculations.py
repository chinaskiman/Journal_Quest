"""Pure derived-value engine - the single source of truth for every
calculated field of the Journal.

Excel column references (from the source workbook)::

    J  = SL ATR Multiplier     L  = R:R (planned)          Z  = Final R:R
    AC = Net PnL               AD = Status                  AE = Duration
    AG = Win Streak (helper)   AH = Loss Streak (helper)

Net PnL model (user-confirmed): the workbook's hardcoded AC column tracks
``Final R:R x Risk - Commission + Swap`` (risk-based money management), not
the price-delta formula written in the empty rows of the sheet.  We
implement the risk-based model, which reproduces the workbook's Win/Loss
statuses and analytics.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Optional


# ---------------------------------------------------------------------------
# SL ATR Multiplier  (Excel J)
# ---------------------------------------------------------------------------
def compute_sl_atr_multiplier(
    entry_price: float | None, sl_price: float | None, atr: float | None
) -> float | None:
    """=IF(OR(H="",I="",R="",R=0),"",ABS(H-I)/R)"""
    if entry_price is None or sl_price is None or atr is None or atr == 0:
        return None
    return abs(entry_price - sl_price) / atr


def _risk_reward(
    entry_price: float | None,
    sl_price: float | None,
    target_price: float | None,
    direction: str | None,
) -> float | None:
    """Shared guts of planned R:R (L) and Final R:R (Z).

    Excel::

        =IF(OR(H="",I="",K=""),"",
         IF(F="Short",
           IF((I-H)<=0,"",(H-K)/(I-H)),
           IF((H-I)<=0,"",(K-H)/(H-I))))
    """
    if entry_price is None or sl_price is None or target_price is None:
        return None
    if direction == "Short":
        denominator = sl_price - entry_price
        if denominator <= 0:
            return None
        return (entry_price - target_price) / denominator
    denominator = entry_price - sl_price
    if denominator <= 0:
        return None
    return (target_price - entry_price) / denominator


# ---------------------------------------------------------------------------
# Planned R:R  (Excel L)
# ---------------------------------------------------------------------------
def compute_planned_rr(
    entry_price: float | None,
    sl_price: float | None,
    tp_price: float | None,
    direction: str | None,
) -> float | None:
    return _risk_reward(entry_price, sl_price, tp_price, direction)


# ---------------------------------------------------------------------------
# Realized / Final R:R  (Excel Z)
# ---------------------------------------------------------------------------
def compute_final_rr(
    entry_price: float | None,
    sl_price: float | None,
    closing_price: float | None,
    direction: str | None,
) -> float | None:
    return _risk_reward(entry_price, sl_price, closing_price, direction)



# ---------------------------------------------------------------------------
# Net PnL  (Excel AC) - risk-based model
# ---------------------------------------------------------------------------
def compute_net_pnl(
    final_rr: float | None,
    risk: float | None,
    commission: float | None,
    swap: float | None,
) -> float | None:
    """Net PnL = Final R:R x Risk - Commission + Swap (blank when
    Final R:R or Risk is missing)."""
    if final_rr is None or risk is None:
        return None
    return final_rr * risk - (commission or 0.0) + (swap or 0.0)


# ---------------------------------------------------------------------------
# Status  (Excel AD)
# ---------------------------------------------------------------------------
def compute_status(
    symbol: str | None,
    closing_price: float | None,
    net_pnl: float | None,
) -> Optional[str]:
    """=IF(B="","",IF(W="","Open",IF(AC="","Open",
    IF(AC>0,"Win",IF(AC<0,"Loss","BE")))))"""
    if symbol is None or symbol == "":
        return None
    if closing_price is None:
        return "Open"
    if net_pnl is None:
        return "Open"
    if net_pnl > 0:
        return "Win"
    if net_pnl < 0:
        return "Loss"
    return "BE"


# ---------------------------------------------------------------------------
# Duration  (Excel AE)
# ---------------------------------------------------------------------------
def compute_duration_seconds(
    opening_day: dt.date | None,
    opening_time: dt.time | None,
    closing_day: dt.date | None,
    closing_time: dt.time | None,
) -> int | None:
    """=(U+V)-(C+D) - blank unless all four parts are present."""
    if (
        opening_day is None
        or opening_time is None
        or closing_day is None
        or closing_time is None
    ):
        return None
    start = dt.datetime.combine(opening_day, opening_time)
    end = dt.datetime.combine(closing_day, closing_time)
    return int((end - start).total_seconds())


def format_duration(seconds: int | None) -> Optional[str]:
    """Human friendly rendering, e.g. ``3d 10h 45m`` / ``5h 0m``."""
    if seconds is None:
        return None
    sign = "-" if seconds < 0 else ""
    total = abs(int(seconds))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return sign + " ".join(parts)


# ---------------------------------------------------------------------------
# Derive everything for one trade row
# ---------------------------------------------------------------------------
def derive_trade(row: dict[str, Any]) -> dict[str, Any]:
    """Return every derived field for one trade row (a plain dict of the
    input columns).  ``row`` itself is not mutated."""
    entry = row.get("entry_price")
    sl = row.get("sl_price")
    tp = row.get("tp_price")
    close = row.get("closing_price")
    direction = row.get("direction")

    final_rr = compute_final_rr(entry, sl, close, direction)
    net_pnl = compute_net_pnl(
        final_rr, row.get("risk"), row.get("commission"), row.get("swap")
    )
    seconds = compute_duration_seconds(
        row.get("opening_day"),
        row.get("opening_time"),
        row.get("closing_day"),
        row.get("closing_time"),
    )
    return {
        "sl_atr_multiplier": compute_sl_atr_multiplier(entry, sl, row.get("atr")),
        "planned_rr": compute_planned_rr(entry, sl, tp, direction),
        "final_rr": final_rr,
        "net_pnl": net_pnl,
        "status": compute_status(row.get("symbol"), close, net_pnl),
        "duration_seconds": seconds,
        "duration_display": format_duration(seconds),
    }


def attach_streaks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute Win/Loss streak helpers strictly by journal row order.

    Excel (intended semantics; the broken ``#REF!`` variant in the first
    data row is deliberately NOT reproduced)::

        =IF(AD="Win", IF(ISNUMBER(AG_prev), AG_prev+1, 1), 0)

    Rows may be supplied in any order; they are sorted by ``seq`` internally
    so the caller can never accidentally feed a filtered or re-sorted view.
    """
    win = 0
    loss = 0
    for row in sorted(rows, key=lambda r: r.get("seq") or 0):
        if row.get("status") == "Win":
            win += 1
        else:
            win = 0
        if row.get("status") == "Loss":
            loss += 1
        else:
            loss = 0
        row["win_streak"] = win
        row["loss_streak"] = loss
    return rows