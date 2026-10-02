"""Unit tests for the pure calculation engine."""
from __future__ import annotations

import datetime as dt

from app.calculations import (
    attach_streaks,
    compute_duration_seconds,
    compute_final_rr,
    compute_net_pnl,
    compute_planned_rr,
    compute_sl_atr_multiplier,
    compute_status,
    derive_trade,
    format_duration,
)


def _d(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def _t(text: str) -> dt.time:
    return dt.time.fromisoformat(text)


# ---------------------------------------------------------------- planned R:R
def test_planned_rr_long_winner():
    assert compute_planned_rr(100, 95, 115, "Long") == 3.0  # (115-100)/(100-95)


def test_planned_rr_short_winner():
    # (100-85)/(105-100)
    assert compute_planned_rr(100, 105, 85, "Short") == 3.0


def test_planned_rr_partial_tp():
    # half way to target -> 1.5
    assert compute_planned_rr(100, 95, 107.5, "Long") == 1.5


def test_planned_rr_blank_tp():
    assert compute_planned_rr(100, 95, None, "Long") is None


def test_planned_rr_blank_sl():
    assert compute_planned_rr(100, None, 115, "Long") is None


def test_planned_rr_invalid_long_geometry():
    # long with SL above entry -> invalid
    assert compute_planned_rr(100, 105, 115, "Long") is None


def test_planned_rr_invalid_short_geometry():
    # short with SL below entry -> invalid
    assert compute_planned_rr(100, 95, 80, "Short") is None


def test_planned_rr_sl_equals_entry():
    assert compute_planned_rr(100, 100, 120, "Long") is None


# ---------------------------------------------------------------- final R:R
def test_final_rr_long_win():
    assert compute_final_rr(100, 95, 110, "Long") == 2.0


def test_final_rr_short_win():
    assert compute_final_rr(100, 105, 90, "Short") == 2.0


def test_final_rr_long_loss_beyond_sl():
    assert compute_final_rr(100, 95, 92.5, "Long") == -1.5


def test_final_rr_short_loss_at_sl():
    assert compute_final_rr(100, 105, 105, "Short") == -1.0


def test_final_rr_break_even():
    assert compute_final_rr(100, 95, 100, "Long") == 0.0


def test_final_rr_open_trade():
    assert compute_final_rr(100, 95, None, "Long") is None


# ---------------------------------------------------------- SL ATR multiplier
def test_sl_atr_multiplier_basic():
    assert compute_sl_atr_multiplier(100, 95, 2.5) == 2.0


def test_sl_atr_multiplier_zero_atr():
    assert compute_sl_atr_multiplier(100, 95, 0) is None


def test_sl_atr_multiplier_missing_values():
    assert compute_sl_atr_multiplier(None, 95, 2.5) is None
    assert compute_sl_atr_multiplier(100, None, 2.5) is None
    assert compute_sl_atr_multiplier(100, 95, None) is None


# ------------------------------------------------------------------- net PnL
def test_net_pnl_risk_based():
    # 2R x 50 - 1.5 + 0.25 = 98.75
    assert compute_net_pnl(2.0, 50, 1.5, 0.25) == 98.75


def test_net_pnl_blank_final_rr():
    assert compute_net_pnl(None, 50, 1.0, 0) is None


def test_net_pnl_blank_risk():
    assert compute_net_pnl(2.0, None, 1.0, 0) is None


def test_net_pnl_missing_commission_swap_treated_as_zero():
    assert compute_net_pnl(1.0, 25, None, None) == 25.0


def test_net_pnl_negative_commission():
    # broker credit: -1R x 50 - (-0.08) = -49.92
    assert compute_net_pnl(-1.0, 50, -0.08, 0) == -49.92


# -------------------------------------------------------------------- status
def test_status_win():
    assert compute_status("EURUSD", 110, 5.0) == "Win"


def test_status_loss():
    assert compute_status("EURUSD", 90, -5.0) == "Loss"


def test_status_break_even():
    assert compute_status("EURUSD", 100, 0.0) == "BE"


def test_status_open_without_closing_price():
    assert compute_status("EURUSD", None, None) == "Open"


def test_status_open_without_net_pnl():
    assert compute_status("EURUSD", 110, None) == "Open"


def test_status_blank_symbol():
    assert compute_status("", 110, 5.0) is None
    assert compute_status(None, 110, 5.0) is None


# ------------------------------------------------------------------ duration
def test_duration_same_day():
    seconds = compute_duration_seconds(_d("2026-09-20"), _t("10:45"), _d("2026-09-20"), _t("13:30"))
    assert seconds == 9900


def test_duration_multi_day():
    seconds = compute_duration_seconds(_d("2026-09-15"), _t("10:45"), _d("2026-09-18"), _t("21:30"))
    assert seconds == 297900  # 3d 10h 45m
    assert format_duration(seconds) == "3d 10h 45m"


def test_duration_open_trade():
    assert compute_duration_seconds(_d("2026-09-20"), _t("10:45"), None, None) is None


def test_duration_missing_time():
    assert compute_duration_seconds(_d("2026-09-20"), None, _d("2026-09-21"), _t("10:00")) is None


def test_duration_display():
    assert format_duration(18000) == "5h"
    assert format_duration(None) is None


# ------------------------------------------------------------------- streaks
def _streak_rows(statuses):
    return [{"seq": i, "status": s} for i, s in enumerate(statuses, start=1)]


def test_streak_runs():
    rows = _streak_rows(["Win", "Win", "Win", "Loss", "Loss", "Win"])
    attach_streaks(rows)
    assert [r["win_streak"] for r in rows] == [1, 2, 3, 0, 0, 1]
    assert [r["loss_streak"] for r in rows] == [0, 0, 0, 1, 2, 0]


def test_streak_open_rows_reset_both():
    rows = _streak_rows(["Win", "Open", "Loss", "Open", "Win"])
    attach_streaks(rows)
    assert [r["win_streak"] for r in rows] == [1, 0, 0, 0, 1]
    assert [r["loss_streak"] for r in rows] == [0, 0, 1, 0, 0]


def test_streaks_independent_of_caller_order():
    rows = _streak_rows(["Win", "Win", "Loss"])
    shuffled = [rows[2], rows[0], rows[1]]
    attach_streaks(shuffled)
    by_seq = sorted(shuffled, key=lambda r: r["seq"])
    assert [r["win_streak"] for r in by_seq] == [1, 2, 0]
    assert [r["loss_streak"] for r in by_seq] == [0, 0, 1]


def test_streak_immune_to_filtering():
    # the streak of row 3 is computed over the FULL journal, even when a UI
    # view happens to filter earlier rows out.
    rows = _streak_rows(["Win", "Win", "Win", "Loss"])
    attach_streaks(rows)
    filtered_view = [r for r in rows if r["seq"] != 1]
    assert filtered_view[1]["win_streak"] == 3  # row 3 still counts rows 1-2


# --------------------------------------------------------------- derive_trade
def test_derive_trade_full_row():
    row = {
        "symbol": "EURUSD",
        "direction": "Long",
        "entry_price": 100.0,
        "sl_price": 95.0,
        "tp_price": 115.0,
        "closing_price": 110.0,
        "risk": 50.0,
        "commission": 1.5,
        "swap": 0.25,
        "atr": 2.5,
    }
    derived = derive_trade(row)
    assert derived["sl_atr_multiplier"] == 2.0
    assert derived["planned_rr"] == 3.0
    assert derived["final_rr"] == 2.0
    assert derived["net_pnl"] == 98.75
    assert derived["status"] == "Win"


def test_derive_trade_open():
    derived = derive_trade(
        {"symbol": "EURUSD", "direction": "Long", "entry_price": 100.0,
         "sl_price": 95.0, "tp_price": 115.0, "risk": 50.0}
    )
    assert derived["final_rr"] is None
    assert derived["net_pnl"] is None
    assert derived["status"] == "Open"


def test_derive_trade_be():
    derived = derive_trade(
        {"symbol": "EURUSD", "direction": "Long", "entry_price": 100.0,
         "sl_price": 95.0, "closing_price": 100.0, "risk": 50.0}
    )
    assert derived["net_pnl"] == 0.0
    assert derived["status"] == "BE"
