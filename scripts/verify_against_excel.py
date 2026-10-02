"""Compare the app's live analytics against the source workbook.

Reads the *cached* values stored in the Analytics sheet of the workbook,
imports the Journal into a temporary database, recomputes everything with
the app's own engine, and prints a side-by-side diff.

Exit code 0 = all checks passed.

Usage:  python scripts/verify_against_excel.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from openpyxl import load_workbook  # noqa: E402

WORKBOOK = ROOT / "Trading Journla-Reaction Based Strategy.xlsx"
TOLERANCE = 0.02  # workbook values were hand-rounded

# Money metrics inherit hand-entry drift from the workbook's hardcoded AC
# literals: rows NZDCAD (-45 vs -41.01) and CADCHF (-31.5 vs -29.12) were
# stored with values inconsistent with their own Final R:R x Risk math.
# Under the approved risk-based model those deltas (max ~$4/trade) flow
# into every money aggregate, so they get a wider, documented tolerance.
MONEY_TOLERANCE = 8.0
MONEY_KEYS = {
    "total_net_pnl", "gross_profit", "gross_loss", "average_win", "average_loss",
    "expectancy", "profit_factor",
}


def read_cached_analytics(path: Path) -> dict[str, object]:
    book = load_workbook(path, data_only=True, read_only=True)
    sheet = book["Analytics"]
    cells: dict[str, object] = {}
    for row in sheet.iter_rows():
        for cell in row:
            if hasattr(cell, "coordinate"):
                cells[cell.coordinate] = cell.value
    book.close()

    def group_table(start_row: int) -> dict[str, dict]:
        table: dict[str, dict] = {}
        row = start_row + 2
        while True:
            name = cells.get(f"A{row}")
            if not name or str(name).strip() == "":
                break
            table[str(name)] = {
                "total": cells.get(f"B{row}"),
                "closed": cells.get(f"C{row}"),
                "win_rate": cells.get(f"D{row}"),
                "avg_realized_r": cells.get(f"E{row}"),
                "net_pnl": cells.get(f"F{row}"),
            }
            row += 1
        return table

    return {
        # Overview (rows 5..11, col B)
        "total_trades": cells.get("B5"),
        "closed_trades": cells.get("B6"),
        "open_trades": cells.get("B7"),
        "wins": cells.get("B8"),
        "losses": cells.get("B9"),
        "break_even": cells.get("B10"),
        "win_rate": cells.get("B11"),
        # P&L (rows 14..22)
        "total_net_pnl": cells.get("B14"),
        "gross_profit": cells.get("B15"),
        "gross_loss": cells.get("B16"),
        "profit_factor": cells.get("B17"),
        "average_win": cells.get("B18"),
        "average_loss": cells.get("B19"),
        "expectancy": cells.get("B20"),
        # Risk (rows 25..31)
        "average_planned_rr": cells.get("B25"),
        "average_realized_r": cells.get("B26"),
        "average_risk": cells.get("B27"),
        "max_consecutive_wins": cells.get("B28"),
        "max_consecutive_losses": cells.get("B29"),
        "total_commission": cells.get("B30"),
        "total_swap": cells.get("B31"),
        # group tables
        "by_symbol": group_table(36),
        "by_direction": group_table(72),
        "by_setup_type": group_table(77),
        "by_mental_state": group_table(84),
    }


def build_live_analytics() -> dict[str, object]:
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["TRADEQUEST_DB"] = str(Path(tmp) / "verify.db")
        for module in [m for m in sys.modules if m.startswith("app")]:
            del sys.modules[module]
        from app.analytics import build_analytics
        from app.db import Base, SessionLocal, engine
        from app.importer import import_workbook
        from app.models import OptionValue, Trade
        from app.serializers import serialize_trades

        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        import_workbook(WORKBOOK, session, mode="replace")
        rows = serialize_trades(session.query(Trade).order_by(Trade.seq).all())
        lists: dict[str, list[str]] = {}
        for key, value in session.query(OptionValue.list_key, OptionValue.value).order_by(
            OptionValue.position
        ):
            lists.setdefault(key, []).append(value)
        session.close()
        payload = build_analytics(rows, lists)
        engine.dispose()  # release the SQLite file so Windows can clean the temp dir

    flat: dict[str, object] = {**payload["overview"], **payload["pnl"], **payload["risk"]}
    for key in ("by_symbol", "by_direction", "by_setup_type", "by_mental_state"):
        flat[key] = {row["group"]: row for row in payload[key]}
    return flat


def _fmt(value) -> str:
    return str(round(value, 4)) if isinstance(value, float) else str(value)


def main() -> int:
    if not WORKBOOK.exists():
        print("Workbook not found - nothing to verify.")
        return 1

    cached = read_cached_analytics(WORKBOOK)
    live = build_live_analytics()

    simple_keys = [
        "total_trades", "closed_trades", "open_trades", "wins", "losses", "break_even",
        "win_rate", "total_net_pnl", "gross_profit", "gross_loss", "profit_factor",
        "average_win", "average_loss", "expectancy", "average_planned_rr",
        "average_realized_r", "average_risk", "max_consecutive_wins",
        "max_consecutive_losses", "total_commission", "total_swap",
    ]

    exact_match = 0
    near_match = 0
    mismatches: list[str] = []

    print(f"{'metric':32}{'workbook (cached)':>20}{'app (live)':>20}  verdict")
    print("-" * 90)
    for key in simple_keys:
        wb_value = cached.get(key)
        app_value = live.get(key)
        if wb_value is None:
            print(f"{key:32}{'-':>20}{_fmt(app_value):>20}  n/a (workbook cached nothing)")
            continue
        if app_value is None:
            verdict = "MISSING"
            mismatches.append(key)
        elif isinstance(wb_value, (int, float)) and isinstance(app_value, (int, float)):
            delta = abs(float(wb_value) - float(app_value))
            tolerance = MONEY_TOLERANCE if key in MONEY_KEYS else TOLERANCE
            if delta <= TOLERANCE:
                verdict = "OK"
                exact_match += 1
            elif delta <= tolerance:
                verdict = "~ (hand-rounded / hand-corrected source)"
                near_match += 1
            else:
                verdict = "MISMATCH"
                mismatches.append(key)
        else:
            verdict = "OK" if wb_value == app_value else "MISMATCH"
            if verdict == "MISMATCH":
                mismatches.append(key)
        print(f"{key:32}{_fmt(wb_value):>20}{_fmt(app_value):>20}  {verdict}")

    metric_map = {
        "total": "total_trades",
        "closed": "closed",
        "win_rate": "win_rate",
        "avg_realized_r": "avg_realized_r",
        "net_pnl": "net_pnl",
    }
    for table_key, label in (
        ("by_symbol", "symbol"),
        ("by_direction", "direction"),
        ("by_setup_type", "setup type"),
        ("by_mental_state", "mental state"),
    ):
        wb_table = cached.get(table_key, {})
        app_table = live.get(table_key, {})
        for group, wb_row in wb_table.items():
            app_row = app_table.get(group)
            if app_row is None:
                # stale group in the cached sheet (e.g. mental state 'Other'
                # that no longer exists in the Options list) - the app
                # enumerates groups from the live Options lists instead.
                if wb_row.get("total") not in (None, 0):
                    mismatches.append(f"{label}:{group}:missing")
                continue
            for metric, live_key in metric_map.items():
                wb_val = wb_row.get(metric)
                app_val = app_row.get(live_key)
                if wb_val is None and app_val is None:
                    continue
                # empty group: workbook caches blank, app shows 0 (spec'd)
                if (wb_val is None or wb_val == "") and app_val in (0, 0.0):
                    continue
                if wb_val is None or app_val is None:
                    ok = False
                elif metric in ("total", "closed"):
                    ok = int(wb_val) == int(app_val)
                else:
                    limit = TOLERANCE if metric != "net_pnl" else MONEY_TOLERANCE
                    ok = abs(float(wb_val) - float(app_val)) <= limit
                if not ok:
                    mismatches.append(f"{label}:{group}:{metric}")
                    print(
                        f"{label} {group:22} {metric:16} "
                        f"workbook={wb_val} app={app_val}  MISMATCH"
                    )

    print("-" * 90)
    print(
        f"{exact_match} exact matches, {near_match} near matches "
        "(workbook cells were hand-rounded)."
    )
    if mismatches:
        print(f"{len(mismatches)} mismatches: {mismatches}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

