"""Phase 3 end-to-end smoke test against the REAL local backend.

Starts the actual uvicorn server (app2.main:app) with a throw-away database,
then drives the full journaling workflow over HTTP exactly like the React UI
does, and finally verifies the built SPA is served on the same port.

Checks (all against live server responses - no frontend mocks):
* fresh database dashboard is honest zeros;
* settings CRUD (symbols/setups) incl. duplicate rejection;
* Quick Capture of a closed trade with manual P&L echoed verbatim;
* mutation feedback: trade +20, quick review +15, deep review +30,
  lessons +10 each up to the 3-per-review cap (4th lesson stored, no XP);
* emotional +10 first entry of the day / +2 afterwards, daily +15, weekly +30;
* level-up payload appears exactly when the ledger crosses a threshold;
* quest claim is explicit and server-priced (JM-01 = +25), double claim
  refused, deferred and undecided rewards never claimable;
* edits award nothing (no XP keys on PATCH responses);
* screenshot endpoint fails closed without TRADEQUEST2_SCREENSHOT_DIRS;
* SPA index + client-side deep links + hashed assets are served from 8001
  while /api/* keeps returning JSON;
* backup endpoint works and the smoke copy is removed afterwards.

Usage (from the repo root, venv python):
    backend\\.venv\\Scripts\\python.exe scripts\\smoke_phase3_v2.py
Exit code 0 = all checks passed.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

TOTAL_CHECKS = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global TOTAL_CHECKS
    TOTAL_CHECKS += 1
    if condition:
        print(f"  [ok] {label}")
    else:
        FAILURES.append(label)
        print(f"  [FAIL] {label} {detail}")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(base: str, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/api/system/health", timeout=2):
                return True
        except Exception:  # noqa: BLE001 - still starting
            time.sleep(0.25)
    return False


def request(base: str, method: str, path: str, payload: dict | None = None):
    """Return (status, parsed_body_or_text)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:  # 4xx/5xx are expected in some checks
        raw, status = exc.read().decode("utf-8", "replace"), exc.code
        content_type = exc.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError:
            return status, raw
    return status, raw


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    workdir = Path(tempfile.mkdtemp(prefix="tq2_smoke_"))
    db_path = workdir / "tradequest_v2_smoke.db"
    png_path = workdir / "shot.png"
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    env = os.environ.copy()
    env["TRADEQUEST2_DB"] = str(db_path)
    env.pop("TRADEQUEST2_SCREENSHOT_DIRS", None)  # prove fail-closed default
    env.pop("TRADEQUEST2_STATIC_DIR", None)       # use frontend_v2/dist

    log = (workdir / "uvicorn.log").open("w", encoding="utf-8")
    print(f"Starting backend on {base} (db={db_path.name}) ...")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app2.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND), env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        if not wait_for_server(base):
            print("  [FAIL] server did not become healthy - see uvicorn log")
            return 1
        trade_id, today, week = run_checks(base, db_path, png_path, workdir)
        run_checks_part2(base, trade_id, today, week)
        run_checks_part3(base, trade_id, png_path, workdir)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            server.kill()
        log.close()
        shutil.rmtree(workdir, ignore_errors=True)
        check("throw-away database and backups removed",
              not db_path.exists() and not workdir.exists())

    print(f"\n{TOTAL_CHECKS - len(FAILURES)}/{TOTAL_CHECKS} checks passed")
    if FAILURES:
        print("FAILED:")
        for item in FAILURES:
            print(f"  - {item}")
        return 1
    print("Phase 3 smoke test: ALL CHECKS PASSED")
    return 0


def run_checks(base: str, db_path: Path, png_path: Path, workdir: Path) -> None:
    now = datetime.now().replace(microsecond=0)
    opened = (now - timedelta(hours=3)).isoformat()
    closed = (now - timedelta(hours=1)).isoformat()
    today = now.date().isoformat()
    iso_year, iso_week, _ = now.isocalendar()
    week = f"{iso_year}-W{iso_week:02d}"

    print("\n1. Fresh database / dashboard")
    status, dash = request(base, "GET", "/api/dashboard")
    check("dashboard reachable", status == 200, str(status))
    check("fresh total_xp == 0", dash["pilot"]["total_xp"] == 0)
    check("fresh level == 1", dash["pilot"]["level"] == 1)
    check("fresh journal counts are 0",
          dash["journal"]["trades_total"] == 0
          and dash["journal"]["lessons"] == 0, json.dumps(dash["journal"]))
    check("no fabricated activity", dash["recent_activity"] == [])
    check("no quests completed yet", dash["quests"]["completed_count"] == 0)

    print("\n2. Settings (symbols / setups / emotions)")
    status, _ = request(base, "POST", "/api/settings/symbols", {"name": "XAUUSD"})
    check("symbol created (201)", status == 201, str(status))
    status, _ = request(base, "POST", "/api/settings/setups", {"name": "Breakout"})
    check("setup created (201)", status == 201, str(status))
    status, _ = request(base, "POST", "/api/settings/symbols", {"name": "XAUUSD"})
    check("duplicate name rejected (409)", status == 409, str(status))
    # Emotions are the same curated list pattern: entries must exist first.
    for label in ("Focused", "Calm"):
        status, _ = request(base, "POST", "/api/settings/emotions", {"name": label})
        check(f"emotion '{label}' created (201)", status == 201, str(status))
    status, body = request(base, "POST", "/api/emotional-entries",
                           {"emotion": "Not Configured", "intensity": 3})
    check("unconfigured emotion refused (422)", status == 422, str(status))
    check("refusal points at Settings -> Emotions",
          "Settings" in json.dumps(body), str(body)[:120])

    print("\n3. Quick Capture: closed trade with manual P&L")
    status, trade = request(base, "POST", "/api/trades", {
        "symbol": "XAUUSD", "setup": "Breakout", "direction": "long",
        "opened_at": opened, "status": "closed", "closed_at": closed,
        "result": "win", "user_pnl": 123.45, "entry_price": 2400.5,
        "exit_price": 2405.25, "thesis": "smoke test",
    })
    check("trade created (201)", status == 201, str(status))
    trade_id = trade.get("id")
    check("creation feedback xp_awarded == 20",
          trade.get("xp_awarded") == 20, json.dumps(trade))
    check("no level-up at 20 XP", trade.get("level_up") is None)
    check("manual P&L echoed verbatim", trade.get("user_pnl") == 123.45)
    check("label snapshot stored", trade.get("symbol_label") == "XAUUSD")

    print("\n4. Edits never award XP")
    status, edited = request(base, "PATCH", f"/api/trades/{trade_id}",
                             {"notes": "edited in smoke test"})
    check("trade PATCH returns TradeOut", status == 200, str(status))
    check("no XP keys on PATCH response",
          "xp_awarded" not in edited and "level_up" not in edited)
    return trade_id, today, week


def run_checks_part2(base: str, trade_id: int, today: str, week: str) -> None:
    print("\n5. Quick Review (+15)")
    status, quick = request(base, "POST", f"/api/trades/{trade_id}/quick-review", {
        "followed_plan": "yes", "execution_rating": 4,
        "went_well": "waited for the retest", "improve": "smaller size",
    })
    check("quick review created (201)", status == 201, str(status))
    check("quick review xp_awarded == 15",
          quick.get("xp_awarded") == 15, json.dumps(quick))

    print("\n6. Deep Review (+30) and the 3-lesson XP cap")
    status, deep = request(base, "POST", f"/api/trades/{trade_id}/deep-review", {
        "plan_review": "plan ok", "execution_review": "entry early",
        "risk_review": "risk respected", "emotions_review": "calm",
        "mistakes": "none", "grade": "B", "key_takeaway": "wait for retest",
        "lessons": [{"text": f"lesson {i}"} for i in range(1, 5)],
    })
    check("deep review created (201)", status == 201, str(status))
    check("deep review xp = 30 + 3 capped lessons = 60",
          deep.get("xp_awarded") == 60, json.dumps(deep.get("xp_awarded")))
    check("all 4 lessons stored, only 3 paid",
          len(deep.get("lessons", [])) == 4, str(len(deep.get("lessons", []))))
    status, lessons = request(base, "GET", "/api/lessons?source_type=deep")
    check("lesson list total == 4", lessons.get("total") == 4, json.dumps(lessons))

    print("\n7. Emotional entry, Daily and Weekly reviews")
    status, emo = request(base, "POST", "/api/emotional-entries", {
        "emotion": "Focused", "intensity": 4, "trade_id": trade_id,
        "trigger": "retest held", "body": "steady hands",
    })
    check("emotional entry created (201)", status == 201, str(status))
    check("first emotional entry of the day = +10",
          emo.get("xp_awarded") == 10, json.dumps(emo.get("xp_awarded")))
    check("100-XP threshold crossed -> level 2 reported",
          (emo.get("level_up") or {}).get("level") == 2,
          json.dumps(emo.get("level_up")))
    status, emo2 = request(base, "POST", "/api/emotional-entries", {
        "emotion": "Calm", "intensity": 3,
    })
    check("second entry of the day = +2",
          emo2.get("xp_awarded") == 2, json.dumps(emo2.get("xp_awarded")))

    status, daily = request(base, "POST", f"/api/daily-reviews/{today}",
                            {"energy": 4, "focus": 4, "mood": 5,
                             "reflection": "good session"})
    check("daily review created (201)", status == 201, str(status))
    check("daily review xp_awarded == 15",
          daily.get("xp_awarded") == 15, json.dumps(daily.get("xp_awarded")))
    status, weekly = request(base, "POST", f"/api/weekly-reviews/{week}",
                             {"highlights": "discipline", "challenges": "patience",
                              "patterns": "retest entries", "plan_next_week": "same",
                              "advice_to_future_me": "  "})
    check("weekly review created (201)", status == 201, str(status))
    check("weekly review xp_awarded == 30",
          weekly.get("xp_awarded") == 30, json.dumps(weekly.get("xp_awarded")))
    check("blank advice normalised to null",
          weekly.get("advice_to_future_me") is None)

    print("\n8. Quests: explicit claim, deferred and undecided rewards")
    status, quests = request(base, "GET", "/api/quests")
    by_code = {q["code"]: q for q in quests["items"]}
    check("FT-01 (first trade) completed", by_code["FT-01"]["completed_at"] is not None)
    check("FT-01 claimable before claim", by_code["FT-01"]["claimable"] is True)
    check("FT-01 reward is the approved +25", by_code["FT-01"]["reward_xp"] == 25)
    check("all first-time quests completed by the workflow",
          all(by_code[code]["completed_at"] is not None
              for code in ("FT-01", "FT-02", "FT-03", "FT-04",
                           "FT-05", "FT-06", "FT-07")),
          str({c: by_code[c]["completed_at"] for c in ("FT-01", "FT-07")}))
    check("multi-trade target respected (JM-01 'Log 10' not done with 1 trade)",
          by_code["JM-01"]["completed_at"] is None
          and by_code["JM-01"]["claimable"] is False,
          json.dumps(by_code["JM-01"]))
    check("XP-total quest JM-05 completes at 100+ XP",
          by_code["JM-05"]["completed_at"] is not None
          and by_code["JM-05"]["claimable"] is True)
    check("LQ-02 stays deferred", by_code["LQ-02"]["status"] == "deferred")
    check("deferred quest is not claimable", by_code["LQ-02"]["claimable"] is False)
    check("CN rewards remain undecided (None)",
          by_code["CN-01"]["reward_xp"] is None
          and by_code["CN-01"]["claimable"] is False)
    status, claim = request(base, "POST", "/api/quests/FT-01/claim")
    check("claim succeeds (200)", status == 200, str(status))
    check("claim awarded_xp == 25", claim.get("awarded_xp") == 25, json.dumps(claim))
    claimed_quest = claim.get("quest") or {}
    check("quest marked claimed", claimed_quest.get("claimed_at") is not None)
    check("claimed quest is no longer claimable",
          claimed_quest.get("claimable") is False)
    check("claiming does not cross another threshold", claim.get("level_up") is None)
    status, _ = request(base, "POST", "/api/quests/FT-01/claim")
    check("double claim refused (409)", status == 409, str(status))
    status, _ = request(base, "POST", "/api/quests/CN-01/claim")
    check("undecided reward cannot be claimed (409)", status == 409, str(status))


def run_checks_part3(base: str, trade_id: int, png_path: Path, workdir: Path) -> None:
    print("\n9. XP ledger is consistent with the feedback values")
    status, xp = request(base, "GET", "/api/xp")
    expected = 20 + 15 + 60 + 10 + 2 + 15 + 30 + 25
    check(f"total XP == {expected}", xp["total_xp"] == expected, json.dumps(xp))
    check("level matches the thresholds", xp["level"] == 2, json.dumps(xp))
    status, events = request(base, "GET", "/api/xp/events")
    check("ledger rows match the workflow (11)", events["total"] == 11,
          str(events["total"]))
    status, dash = request(base, "GET", "/api/dashboard")
    check("dashboard XP equals /api/xp",
          dash["pilot"]["total_xp"] == xp["total_xp"])
    # Level-payload contract the UI displays verbatim (177 XP -> level 2).
    pilot = dash["pilot"]
    check("dashboard pilot is identical to /api/xp", pilot == xp, json.dumps(pilot))
    check("pilot: 77 XP inside level 2", pilot["current_level_xp"] == 77,
          json.dumps(pilot))
    check("pilot: 73 XP still needed (not the 150-XP span)",
          pilot["next_level_xp_needed"] == 73, json.dumps(pilot))
    check("pilot: next level total is 250", pilot["next_level_total_xp"] == 250)
    check("pilot: in-level + remaining == level span (150)",
          pilot["current_level_xp"] + pilot["next_level_xp_needed"] == 150)
    check("pilot: progress_pct == 51.33 (server-computed)",
          abs(pilot["progress_pct"] - round(77 / 150 * 100, 2)) < 0.01,
          str(pilot["progress_pct"]))
    check("dashboard sees the claimed quest",
          dash["quests"]["claimed_count"] >= 1, json.dumps(dash["quests"]))
    check("dashboard flags today's reviews as done",
          dash["journal"]["daily_review_done_today"] is True
          and dash["journal"]["weekly_review_done_this_week"] is True,
          json.dumps(dash["journal"]))
    check("dashboard counts the reflection records",
          dash["journal"]["quick_reviews"] == 1
          and dash["journal"]["lessons"] == 4
          and dash["journal"]["emotional_entries"] == 2,
          json.dumps(dash["journal"]))

    print("\n10. Achievements: hidden secrets stay hidden")
    status, achievements = request(base, "GET", "/api/achievements")
    items = achievements["items"]
    unlocked = [a for a in items if a["unlocked"]]
    secrets = [a for a in items if a["hidden"]]
    check("achievements listed", status == 200 and len(items) >= 10, str(status))
    check("hidden achievements exist", len(secrets) >= 1)
    check("locked secrets show as ???",
          all(a["name"] == "???" for a in secrets if not a["unlocked"]))
    check("unlocked achievements reveal their real name",
          all(a["name"] != "???" and a["description"] != "Hidden achievement."
              for a in unlocked),
          str([a["code"] for a in unlocked]))
    check("dashboard unlock count matches the gallery",
          dash["achievements"]["unlocked_count"] == len(unlocked),
          f"{dash['achievements']['unlocked_count']} vs {len(unlocked)}")

    print("\n11. Screenshots fail closed (no allow-list configured)")
    status, _ = request(base, "GET", f"/api/trades/{trade_id}/screenshot")
    check("no screenshot on file -> 404", status == 404, str(status))
    status, _ = request(base, "PATCH", f"/api/trades/{trade_id}",
                        {"screenshot_path": str(png_path)})
    check("screenshot path accepted as text", status == 200, str(status))
    status, body = request(base, "GET", f"/api/trades/{trade_id}/screenshot")
    check("unconfigured allow-list refuses the file (422)", status == 422, str(status))
    check("refusal explains the allow-list",
          "TRADEQUEST2_SCREENSHOT_DIRS" in json.dumps(body), str(body)[:140])

    print("\n12. Backup endpoint (isolated next to the throw-away database)")
    project_backups = set()
    if (ROOT / "data" / "backups").is_dir():
        project_backups = {p.name for p in (ROOT / "data" / "backups").glob("*.db")}
    status, backup = request(base, "GET", "/api/system/backup")
    check("backup created (200)", status == 200, str(status))
    # BACKUP_DIR follows the active DB, so a smoke run never touches real data.
    backup_file = workdir / "backups" / str(backup.get("backup"))
    check("backup file written next to the temp database",
          backup_file.is_file(), str(backup_file))
    check("retention is capped at 10", backup.get("kept") == 10)
    still_there = {p.name for p in (ROOT / "data" / "backups").glob("*.db")} \
        if project_backups else set()
    check("project data/backups untouched by the smoke run",
          still_there == project_backups,
          f"{sorted(still_there ^ project_backups)}")

    print("\n13. Built SPA served by the backend on the same port")
    status, index = request(base, "GET", "/")
    check("GET / serves HTML (200)", status == 200, str(status))
    check("index.html contains the app root",
          'id="root"' in index and "Trade Quest" in index, index[:80])
    status, deep = request(base, "GET", "/quests")
    check("deep link /quests falls back to index.html",
          status == 200 and deep == index)
    status, deep2 = request(base, "GET", "/settings")
    check("deep link /settings works too", status == 200 and deep2 == index)
    asset = index.split('src="', 1)[1].split('"', 1)[0] if 'src="' in index else ""
    if asset.startswith("/"):
        status, _ = request(base, "GET", asset)
        check(f"hashed asset {asset} served", status == 200, str(status))
    else:
        check("index references a built asset", False, asset[:60])
    status, _ = request(base, "GET", "/api/system/health")
    check("API still answers next to the SPA (200)", status == 200)
    status, missing = request(base, "GET", "/api/does-not-exist")
    check("unknown API path stays a JSON 404 (never HTML)",
          status == 404 and isinstance(missing, dict) and missing != index,
          str(missing)[:80])


if __name__ == "__main__":
    raise SystemExit(main())
