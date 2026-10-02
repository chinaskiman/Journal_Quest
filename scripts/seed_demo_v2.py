"""Seed a DEMO database for Trade Quest v2 (used for screenshots/demos).

Creates `data/tradequest_v2_demo.db` from scratch and fills it through the
real HTTP API (never by writing tables directly), so XP, quest progress and
achievements end up in exactly the states the app produces.  The user's real
database (`data/tradequest_v2.db`) is never touched.

Usage (from the repo root, venv python):
    backend\\.venv\\Scripts\\python.exe scripts\\seed_demo_v2.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEMO_DB = ROOT / "data" / "tradequest_v2_demo.db"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request(base: str, method: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {path} -> {exc.code}: {detail[:300]}") from None


def main() -> int:
    if DEMO_DB.exists():
        DEMO_DB.unlink()
        print(f"removed previous demo database {DEMO_DB.name}")
    DEMO_DB.parent.mkdir(parents=True, exist_ok=True)

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["TRADEQUEST2_DB"] = str(DEMO_DB)
    env["TRADEQUEST2_STATIC_DIR"] = str(ROOT / "frontend_v2" / "dist")

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app2.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 25
        while time.time() < deadline:
            try:
                request(base, "GET", "/api/system/health")
                break
            except Exception:  # noqa: BLE001 - still starting
                time.sleep(0.25)
        else:
            raise SystemExit("backend did not start")

        seed(base)
        status, xp = request(base, "GET", "/api/xp")
        status, quests = request(base, "GET", "/api/quests")
        claimable = [q["code"] for q in quests["items"] if q["claimable"]]
        claimed = [q["code"] for q in quests["items"] if q["claimed_at"]]
        print(f"\nDemo state: {xp['total_xp']} XP, level {xp['level']} "
              f"({xp['title']}), {len(claimed)} quests claimed, "
              f"claimable now: {', '.join(claimable) or 'none'}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            server.kill()

    print(f"\nDemo database ready: {DEMO_DB}")
    print("Screenshot server command:")
    print(f'  $env:TRADEQUEST2_DB="{DEMO_DB}"')
    print("  backend\\.venv\\Scripts\\python -m uvicorn app2.main:app "
          "--host 127.0.0.1 --port 8011")
    return 0


def seed(base: str) -> None:
    now = datetime.now().replace(microsecond=0)
    iso_year, iso_week, _ = now.isocalendar()

    def days_ago(days: int, hour: int = 9, minute: int = 30) -> str:
        stamp = (now - timedelta(days=days)).replace(
            hour=hour, minute=minute, second=0)
        return stamp.isoformat()

    print("settings ...")
    for name in ("XAUUSD", "EURUSD", "NAS100"):
        request(base, "POST", "/api/settings/symbols", {"name": name})
    for name in ("Breakout Retest", "Trend Pullback", "Range Fade"):
        request(base, "POST", "/api/settings/setups", {"name": name})
    for name in ("Focused", "Calm", "Anxious", "Frustrated", "Impatient"):
        request(base, "POST", "/api/settings/emotions", {"name": name})

    print("trades ...")
    trades = [
        # (symbol, setup, direction, opened, closed, result, pnl, thesis, notes)
        ("XAUUSD", "Breakout Retest", "long", days_ago(21), days_ago(21, 12),
         "win", 180.50,
         "London sweep of the Asian low, then reclaim of the level.",
         "Waited for the retest instead of chasing the first push."),
        ("EURUSD", "Trend Pullback", "short", days_ago(18), days_ago(18, 15),
         "loss", -65.25,
         "Lower-high into the daily supply zone.",
         "Entry was early; the pullback continued for another hour."),
        ("NAS100", "Range Fade", "long", days_ago(14), days_ago(14, 16),
         "breakeven", 0.0,
         "Fade the range low with a tight stop.",
         "Moved to breakeven too fast - the trade later ran without me."),
        ("XAUUSD", "Breakout Retest", "long", days_ago(7), days_ago(7, 13),
         "win", 240.00,
         "Same level as the first XAUUSD trade - it held again.",
         "Size was right; exits followed the plan."),
        ("XAUUSD", "Trend Pullback", "long", days_ago(1), None,
         None, None,
         "Holding the weekly open above the range.",
         "Still open - letting the runner work."),
    ]
    ids: list[int] = []
    for symbol, setup, direction, opened, closed, result, pnl, thesis, notes in trades:
        payload: dict = {
            "symbol": symbol, "setup": setup, "direction": direction,
            "opened_at": opened, "thesis": thesis, "notes": notes,
            "entry_price": None, "user_pnl": pnl,
        }
        if closed:
            payload.update({"status": "closed", "closed_at": closed,
                            "result": result})
        status, trade = request(base, "POST", "/api/trades", payload)
        ids.append(trade["id"])

    print("quick reviews ...")
    request(base, "POST", f"/api/trades/{ids[0]}/quick-review", {
        "followed_plan": "yes", "execution_rating": 5,
        "went_well": "Waited for the retest and sized correctly.",
        "went_wrong": "Nothing material - the plan was followed.",
        "improve": "Journal the exit before the next session starts.",
    })
    request(base, "POST", f"/api/trades/{ids[1]}/quick-review", {
        "followed_plan": "partly", "execution_rating": 3,
        "went_well": "Read the zone correctly.",
        "went_wrong": "Entered before confirmation and sized up.",
        "improve": "Wait for the reaction candle; keep the first size small.",
    })
    request(base, "POST", f"/api/trades/{ids[3]}/quick-review", {
        "followed_plan": "yes", "execution_rating": 4,
        "went_well": "Same setup, better patience - the level was respected.",
        "went_wrong": "Slightly late on the partial exit.",
        "improve": "Scale out at the pre-marked level without hesitating.",
    })

    print("deep review + lessons ...")
    request(base, "POST", f"/api/trades/{ids[1]}/deep-review", {
        "plan_review": "The plan was sound: daily supply, lower high, stop "
                       "above the swing.",
        "execution_review": "Entry was 20 minutes early - before the "
                            "confirmation candle closed.",
        "risk_review": "Risk was 1R as intended; no widening of the stop.",
        "emotions_review": "Impatient after two quiet sessions - wanted action.",
        "mistakes": "Entered on anticipation rather than confirmation.",
        "grade": "C",
        "key_takeaway": "Anticipation entries feel productive but are just "
                        "impatience with a better story.",
        "lessons": [
            {"text": "Confirmation first: the candle close is the trigger, "
                     "not the touch."},
            {"text": "Two quiet sessions are still sessions - no need to "
                     "force a trade."},
            {"text": "Same 1R risk kept the loss small even when the read "
                     "was wrong."},
        ],
    })

    print("emotional journal ...")
    for emotion, intensity, when, trade_id, trigger, body in [
        ("Impatient", 4, days_ago(2, 11), ids[1],
         "Third quiet hour in a row",
         "Wanted the market to move for me instead of waiting for it."),
        ("Calm", 2, days_ago(2, 16), ids[1],
         "After closing the loss",
         "Accepted the loss quickly once I saw the entry was early."),
        ("Focused", 5, days_ago(1, 10), ids[3],
         "Pre-market plan was clear",
         "Nothing to prove today - the level either holds or it does not."),
        ("Anxious", 3, days_ago(0, 8), None,
         "Position still open",
         "Normal open-trade nerves; the stop is defined, so nothing to do."),
    ]:
        request(base, "POST", "/api/emotional-entries", {
            "emotion": emotion, "intensity": intensity,
            "occurred_at": when, "trade_id": trade_id,
            "trigger": trigger, "body": body,
        })

    print("daily reviews ...")
    request(base, "POST", f"/api/daily-reviews/{(now - timedelta(days=2)).date()}", {
        "energy": 3, "focus": 3, "mood": 3,
        "reflection": "Forced the EURUSD short. The read was fine, the timing "
                      "was not - anticipation again.",
    })
    request(base, "POST", f"/api/daily-reviews/{(now - timedelta(days=1)).date()}", {
        "energy": 4, "focus": 5, "mood": 4,
        "reflection": "Slow, patient session. One A+ setup, one clean entry.",
    })
    request(base, "POST", f"/api/daily-reviews/{now.date()}", {
        "energy": 4, "focus": 4, "mood": 4,
        "reflection": "Held the open XAUUSD runner; reviewed last week's "
                      "lessons before the session.",
    })

    print("weekly reviews ...")
    prev_year, prev_week, _ = (now - timedelta(days=7)).isocalendar()
    request(base, "POST",
            f"/api/weekly-reviews/{prev_year}-W{prev_week:02d}", {
                "highlights": "Best week at following the plan - three clean "
                              "entries, no size spikes.",
                "challenges": "Quiet sessions still pull me toward "
                              "anticipation entries.",
                "patterns": "Every win came from a level I had marked the "
                            "evening before.",
                "plan_next_week": "Same routine: mark levels, wait for the "
                                  "retest, one setup per session.",
                "advice_to_future_me": "You already know the level. Your only "
                                       "job is to wait for it.",
            })
    request(base, "POST", f"/api/weekly-reviews/{iso_year}-W{iso_week:02d}", {
        "highlights": "Started journalling the exit before the session ends.",
        "challenges": "One early entry; the rest of the week was disciplined.",
        "plan_next_week": "Keep the pre-market marking routine and the 1R "
                          "risk on every trade.",
        "advice_to_future_me": "Confirmation is not a delay, it is the entry "
                               "itself.",
    })

    print("claiming quests (FT-01..FT-06) ...")
    for code in ("FT-01", "FT-02", "FT-03", "FT-04", "FT-05", "FT-06"):
        request(base, "POST", f"/api/quests/{code}/claim")


if __name__ == "__main__":
    raise SystemExit(main())

