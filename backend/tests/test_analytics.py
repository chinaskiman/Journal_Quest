"""Analytics engine tests."""
from __future__ import annotations

from app.analytics import build_analytics, build_group_rows


def _row(seq, **kwargs):
    base = {
        "seq": seq,
        "symbol": "EURUSD",
        "direction": "Long",
        "setup_type": "Breakout",
        "mental_state": "Calm",
        "closing_price": None,
        "final_rr": None,
        "net_pnl": None,
        "status": "Open",
        "planned_rr": None,
        "risk": None,
        "commission": None,
        "swap": None,
        "win_streak": 0,
        "loss_streak": 0,
    }
    base.update(kwargs)
    return base


ROWS = [
    _row(1, closing_price=110.0, final_rr=2.0, net_pnl=98.75, status="Win",
         planned_rr=3.0, risk=50.0, commission=1.5, swap=0.25, win_streak=1),
    _row(2, closing_price=90.0, final_rr=-1.0, net_pnl=-51.0, status="Loss",
         planned_rr=3.0, risk=50.0, commission=1.0, loss_streak=1),
    _row(3, symbol="XAUUSD", setup_type="Rejection", mental_state="Confident",
         closing_price=2100.0, final_rr=1.0, net_pnl=24.0, status="Win",
         planned_rr=2.0, risk=25.0, commission=1.0, win_streak=1),
    _row(4, symbol="XAUUSD", setup_type="Rejection", mental_state="Confident"),
]

OPTION_LISTS = {
    "symbol": ["EURUSD", "XAUUSD", "AUDCAD"],
    "setup_type": ["Breakout", "Rejection"],
    "mental_state": ["Calm", "Confident"],
}


def test_overview_counts():
    payload = build_analytics(ROWS, OPTION_LISTS)
    assert payload["overview"] == {
        "total_trades": 4,
        "closed_trades": 3,
        "open_trades": 1,
        "wins": 2,
        "losses": 1,
        "break_even": 0,
        "win_rate": 2 / 3,
    }


def test_pnl_section():
    payload = build_analytics(ROWS, OPTION_LISTS)
    pnl = payload["pnl"]
    assert pnl["total_net_pnl"] == 98.75 - 51.0 + 24.0
    assert pnl["gross_profit"] == 98.75 + 24.0
    assert pnl["gross_loss"] == 51.0
    assert pnl["profit_factor"] == (98.75 + 24.0) / 51.0
    assert pnl["average_win"] == (98.75 + 24.0) / 2
    assert pnl["average_loss"] == -51.0
    assert pnl["expectancy"] == (98.75 - 51.0 + 24.0) / 3
    assert pnl["best_trade"] == 98.75
    assert pnl["worst_trade"] == -51.0


def test_risk_section():
    payload = build_analytics(ROWS, OPTION_LISTS)
    risk = payload["risk"]
    assert risk["average_planned_rr"] == (3.0 + 3.0 + 2.0) / 3
    assert risk["average_realized_r"] == (2.0 - 1.0 + 1.0) / 3
    assert risk["average_risk"] == (50.0 + 50.0 + 25.0) / 3
    assert risk["max_consecutive_wins"] == 1
    assert risk["max_consecutive_losses"] == 1
    assert risk["total_commission"] == 3.5
    assert risk["total_swap"] == 0.25


def test_group_rows_enumerate_option_lists_with_zero_for_empty_groups():
    rows = build_group_rows(ROWS, "symbol", OPTION_LISTS["symbol"])
    by_group = {r["group"]: r for r in rows}
    # unused group still shows up with zeros
    assert by_group["AUDCAD"] == {
        "group": "AUDCAD",
        "total_trades": 0,
        "closed": 0,
        "win_rate": None,
        "avg_realized_r": None,
        "net_pnl": 0.0,
    }
    assert by_group["EURUSD"]["total_trades"] == 2
    assert by_group["EURUSD"]["closed"] == 2
    assert by_group["EURUSD"]["win_rate"] == 0.5  # 1 win / 2 closed
    assert by_group["XAUUSD"]["closed"] == 1
    assert by_group["XAUUSD"]["win_rate"] == 1.0


def test_direction_group_fixed_long_short():
    payload = build_analytics(ROWS, OPTION_LISTS)
    groups = {r["group"]: r for r in payload["by_direction"]}
    assert set(groups) == {"Long", "Short"}


def test_equity_curve_cumulative():
    payload = build_analytics(ROWS, OPTION_LISTS)
    curve = payload["equity_curve"]
    # only closed trades, in closing order
    assert [c["net_pnl"] for c in curve] == [98.75, -51.0, 24.0]
    assert curve[-1]["cum_net_pnl"] == 98.75 - 51.0 + 24.0


def test_empty_journal_analytics():
    payload = build_analytics([], {"symbol": ["EURUSD"]})
    assert payload["overview"]["total_trades"] == 0
    assert payload["overview"]["win_rate"] is None
    assert payload["pnl"]["total_net_pnl"] == 0.0
    assert payload["pnl"]["profit_factor"] is None
    assert payload["risk"]["max_consecutive_wins"] == 0
    assert payload["by_symbol"][0]["total_trades"] == 0
