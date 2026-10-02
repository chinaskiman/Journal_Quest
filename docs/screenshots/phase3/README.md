# Trade Quest v2 — Phase 3 screenshots

Full-page captures of every screen, taken from the real app (backend serving
the built SPA on one port) with headless Chrome via
`frontend_v2/scripts/capture-screenshots.mjs`.

The data shown comes from the **demo database**
(`data/tradequest_v2_demo.db`, created by `scripts/seed_demo_v2.py`):
5 trades, 3 quick reviews, 1 deep review with 3 lessons, 4 emotional entries,
3 daily + 2 weekly reviews, 6 quests claimed — 492 XP, level 4
"Deck Observer", 8 achievements unlocked.

| # | File | Screen |
|---|---|---|
| 01 | `01-quest-hub.png` | Quest Hub — level/XP, rewards ready, active quests, today panel, achievements, reflection summary, activity feed, trades awaiting review |
| 02 | `02-trade-journal.png` | Trade Journal — server-side status/symbol filters, list, paging |
| 03 | `03-trade-detail.png` | Trade detail — labels, manual P&L, close/edit actions, reviews, emotional context, screenshot area |
| 04 | `04-quick-capture.png` | Quick Capture — minimal manual entry (no broker/P&L calculation) |
| 05 | `05-quick-review.png` | Quick Review — picker + form filled for the selected trade |
| 06 | `06-deep-review.png` | Deep Review — prefilled review, grade, and the 3-lesson XP-cap messaging |
| 07 | `07-emotional-journal.png` | Emotional Journal — Settings-backed emotion list, intensity pills, entries |
| 08 | `08-daily-review.png` | Daily Review — energy/focus/mood sliders + reflection |
| 09 | `09-weekly-review.png` | Weekly Review — highlights/challenges/patterns/plan/advice |
| 10 | `10-quest-center.png` | Quest Center — ready to claim, in progress, completed & claimed, consistency opt-in, not-yet-available (deferred) |
| 11 | `11-achievements.png` | Achievements — unlocked gallery; locked secrets stay `???` |
| 12 | `12-settings.png` | Settings — symbols/setups/emotions manager |
| 13 | `13-settings-options.png` | Settings → Options — consistency opt-in, screenshot allow-list help, backups |
| 14 | `14-quest-claim-toast.png` | After clicking *Claim reward* — server-confirmed `+25 XP` toast, quest moved to claimed |

`shots.json` records the base URL, timestamp and file list of the run.

## Re-capturing

```powershell
# 1) optional: seed the demo database (never touches data/tradequest_v2.db)
backend\.venv\Scripts\python.exe scripts\seed_demo_v2.py

# 2) serve the app (built SPA + API on one port)
$env:TRADEQUEST2_DB="data\tradequest_v2_demo.db"
backend\.venv\Scripts\python.exe -m uvicorn app2.main:app --host 127.0.0.1 --port 8011

# 3) capture (uses your installed Chrome; no browser download)
cd frontend_v2
npm run screenshots
```

Point it at your own journal instead by skipping step 1 / using
`TRADEQUEST2_DB=data\tradequest_v2.db`, or capture a running dev server with
`npm run screenshots -- --base http://127.0.0.1:5174`.
