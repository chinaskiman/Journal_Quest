"""Analytics engine - recreates the Analytics sheet of the workbook as a
live dashboard payload.

Every figure is computed from the (derived) journal rows; nothing is
stored.  Group values are enumerated from the Options lists so unused
groups still show up with zero/blank values exactly like the spreadsheet.
"""
from __future__ import annotations

import datetime as dt
from statistics import fmean
from typing import Any

DIRECTION_GROUPS = ["Long", "Short"]


def _mean(values: list[float]) -> float | None:
    return fmean(values) if values else None


def build_group_rows(
    rows: list[dict[str, Any]], field: str, group_values: list[str]
) -> list[dict[str, Any]]:
    """One table row per group value.

    Excel equivalents::

        Total Trades   = COUNTIF(<field>, group)
        Closed         = COUNTIFS(<field>, group, W, "<>")
        Win Rate       = COUNTIFS(<field>, group, AD, "Win") / Closed
        Avg Realized R = IFERROR(AVERAGEIFS(Z, <field>, group), "")
        Net P&L        = SUMIFS(AC, <field>, group)
    """
    out: list[dict[str, Any]] = []
    for group in group_values:
        members = [r for r in rows if (r.get(field) or "") == group]
        closed = [r for r in members if r.get("closing_price") is not None]
        wins = sum(1 for r in members if r.get("status") == "Win")
        realized = [r["final_rr"] for r in members if r.get("final_rr") is not None]
        pnls = [r["net_pnl"] for r in members if r.get("net_pnl") is not None]
        out.append(
            {
                "group": group,
                "total_trades": len(members),
                "closed": len(closed),
                "win_rate": (wins / len(closed)) if closed else None,
                "avg_realized_r": _mean(realized),
                "net_pnl": sum(pnls) if pnls else 0.0,
            }
        )
    return out


def _build_equity_curve(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cumulative net P&L over closed trades, in exit order."""
    closed = [
        r
        for r in rows
        if r.get("closing_price") is not None and r.get("net_pnl") is not None
    ]

    def sort_key(r: dict[str, Any]) -> tuple:
        day = r.get("closing_day") or dt.date.min
        time_part = r.get("closing_time") or dt.time(0, 0)
        return (dt.datetime.combine(day, time_part), r.get("seq") or 0)

    closed.sort(key=sort_key)
    cumulative = 0.0
    curve: list[dict[str, Any]] = []
    for r in closed:
        cumulative += r["net_pnl"]
        curve.append(
            {
                "seq": r.get("seq"),
                "symbol": r.get("symbol"),
                "closing_day": r.get("closing_day"),
                "net_pnl": r["net_pnl"],
                "cum_net_pnl": cumulative,
            }
        )
    return curve


def build_analytics(
    rows: list[dict[str, Any]], option_lists: dict[str, list[str]]
) -> dict[str, Any]:
    """Build the full dashboard payload from derived journal rows."""
    # ---- Overview --------------------------------------------------------
    with_symbol = [r for r in rows if r.get("symbol")]
    closed_rows = [r for r in rows if r.get("closing_price") is not None]
    statuses = [r.get("status") for r in rows]
    wins = statuses.count("Win")
    losses = statuses.count("Loss")
    break_even = statuses.count("BE")

    overview = {
        "total_trades": len(with_symbol),
        "closed_trades": len(closed_rows),
        "open_trades": len(with_symbol) - len(closed_rows),
        "wins": wins,
        "losses": losses,
        "break_even": break_even,
        "win_rate": (wins / len(closed_rows)) if closed_rows else None,
    }

    # ---- Profit & Loss ----------------------------------------------------
    pnls = [r["net_pnl"] for r in rows if r.get("net_pnl") is not None]
    positive = [p for p in pnls if p > 0]
    negative = [p for p in pnls if p < 0]
    gross_profit = sum(positive)
    gross_loss = abs(sum(negative))

    pnl = {
        "total_net_pnl": sum(pnls) if pnls else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": (gross_profit / gross_loss) if gross_loss else None,
        "average_win": _mean(positive),
        "average_loss": _mean(negative),
        "expectancy": (sum(pnls) / len(closed_rows)) if closed_rows else None,
        "best_trade": max(pnls) if pnls else None,
        "worst_trade": min(pnls) if pnls else None,
    }

    # ---- Risk & Ratios ---------------------------------------------------
    planned = [r["planned_rr"] for r in rows if r.get("planned_rr") is not None]
    realized = [r["final_rr"] for r in rows if r.get("final_rr") is not None]
    risks = [r["risk"] for r in rows if r.get("risk") is not None]
    commissions = [r["commission"] for r in rows if r.get("commission") is not None]
    swaps = [r["swap"] for r in rows if r.get("swap") is not None]

    risk = {
        "average_planned_rr": _mean(planned),
        "average_realized_r": _mean(realized),
        "average_risk": _mean(risks),
        "max_consecutive_wins": max((r.get("win_streak", 0) for r in rows), default=0),
        "max_consecutive_losses": max(
            (r.get("loss_streak", 0) for r in rows), default=0
        ),
        "total_commission": sum(commissions) if commissions else 0.0,
        "total_swap": sum(swaps) if swaps else 0.0,
    }

    # ---- Performance tables -----------------------------------------------
    groups = {
        "by_symbol": build_group_rows(rows, "symbol", option_lists.get("symbol", [])),
        "by_direction": build_group_rows(rows, "direction", DIRECTION_GROUPS),
        "by_setup_type": build_group_rows(
            rows, "setup_type", option_lists.get("setup_type", [])
        ),
        "by_mental_state": build_group_rows(
            rows, "mental_state", option_lists.get("mental_state", [])
        ),
    }

    return {
        "overview": overview,
        "pnl": pnl,
        "risk": risk,
        **groups,
        "equity_curve": _build_equity_curve(rows),
    }
