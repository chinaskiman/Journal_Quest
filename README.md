# TradeQuest — Trading Journal (Reaction-Based Strategy)

> **Trade Quest v2 (Phase 3) is available: the gamified backend now ships with
> its own React UI.** It is a local-first journaling app (XP, levels, quests,
> achievements, reflection systems) that runs **alongside** the original v1 app
> with its own fresh database (`data/tradequest_v2.db`) — v1, its database and
> its tests are untouched.
> See **PHASE2_REPORT.md** and **Appendix P** in PHASE1_BLUEPRINT.md.
>
> - Launch v2 (single port, UI + API): `start_tradequest_v2.bat` →
>   `http://127.0.0.1:8001` (API docs at `/docs`). The backend serves the built
>   UI from `frontend_v2/dist` when it exists, otherwise it stays API-only.
> - Dev mode: `start_backend_v2_dev.bat` (auto-reload) **and**
>   `start_frontend_v2_dev.bat` (Vite HMR on `http://127.0.0.1:5174`,
>   `/api` proxied to `:8001`)
> - All tests: `run_tests.bat` (v1 + v2 backend: 203, Phase 3 UI: 36)
> - Live end-to-end check: `backend\.venv\Scripts\python scripts\smoke_phase3_v2.py`
>   (79 assertions against the real server + built SPA)
> - One-time setup: `setup_tradequest.bat` (also installs/builds the UI when
>   Node.js is present)
> - **Documentation:** Persian user guide → [`README_FA.md`](README_FA.md);
>   English setup & operations guide (install, configuration, backup, and the
>   *untested* restore procedure) → [`docs/SETUP_AND_OPERATIONS.md`](docs/SETUP_AND_OPERATIONS.md)
>
> The v2 backend never seeds Excel data, never calculates P&L, and never
> awards XP for anything except journaling, reflection, learning and claimed
> quests. **All XP, levels, quest progress and achievements are computed by the
> backend** — the UI only displays what the server returns.

A full-stack trading journal that faithfully reproduces
**Trading Journla-Reaction Based Strategy.xlsx** — its 34-column data model,
dropdown option lists, live formulas and Analytics dashboard — then lets you
manage trades, options and analytics through a modern web UI.

- **Backend**: FastAPI + SQLAlchemy + SQLite (WAL), pure-Python calculation engine
- **Frontend**: React 19 + TypeScript + Vite, TanStack Query/Virtual, Recharts
- **Seed data**: the workbook is imported once on first boot (import only — the
  app never needs it again) — **v1 only; v2 never imports anything**
- **Databases**: `data/tradequest.db` (v1, preserved) and
  `data/tradequest_v2.db` (v2, fresh/empty, created on first v2 start)

---

## Quick start (v1 — unchanged)

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

On first start the API creates `data/tradequest.db` and seeds it from
`Trading Journla-Reaction Based Strategy.xlsx` (11 trades + 5 option lists).

### 2. Frontend

The original v1 UI (`frontend/`) has been **removed**; `frontend_v2/` is now the
project's only frontend. See the v2 section below. The v1 API on port 8000
still works on its own — it simply serves JSON only (its optional SPA mount is
skipped when no build is present).

### 3. Tests & verification

```powershell
cd backend
.venv\Scripts\python -m pytest tests -q              # 79 tests
cd ..
backend\.venv\Scripts\python scripts\bootstrap.py    # manual (re)seed
backend\.venv\Scripts\python scripts\verify_against_excel.py
```

`verify_against_excel.py` re-imports the workbook into a throw-away database
and diffs the app's live analytics against the cached values in the workbook's
Analytics sheet (exit code 0 = pass).

---

## The data model

The `trades` table persists the **25 input columns** of the Journal sheet.
The **9 calculated columns** are never stored — they are recomputed on every
read by `backend/app/calculations.py`, the single source of truth:

| Column | Rule (workbook parity) |
|---|---|
| `#` | journal row order (`seq`); renumbered on delete like Excel rows |
| SL ATR Multiplier | `ABS(entry − SL) / ATR`, blank if ATR missing/0 |
| R:R (planned) | Long `(TP−E)/(E−SL)`, Short `(E−TP)/(SL−E)`, blank on invalid geometry |
| Final R:R | same geometry with closing price instead of TP |
| **Net PnL** | **`Final R:R × Risk − Commission + Swap`** (user-confirmed risk-based model) |
| Status | blank symbol → blank; no close → `Open`; else Win/Loss/BE by sign of Net PnL |
| Duration | `(closing day+time) − (opening day+time)`; blank unless all 4 parts exist |
| Win/Loss Streak | one ordered pass over `seq` — immune to filtering/sorting |

### Why the dashboard shows $258.10 (not the workbook's cached $252.21)

The workbook's Net PnL column is **hardcoded**, and most values were
hand-rounded. Two rows (NZDCAD `-45` and CADCHF `-31.5`) were also stored with
values that don't agree with their own `Final R:R × Risk` math (the formula
gives `-41.01` / `-29.12`). Because you approved the risk-based formula model,
the app always recomputes, so money aggregates drift from the cached literals
by up to ~$6 while all counts, win rates, realized R and streaks match exactly.
The workbook's literal values are preserved read-only in the `source_net_pnl`
audit column and shown in the trade drawer ("Source audit").

Other deliberate deviations (documented, not bugs):

- **`#REF!` streak formulas** in AG2/AH2 — the intended streak semantics are
  implemented instead.
- **XAUUSD's hardcoded R:R of 4** — recomputed from prices (4.151…) per the
  intended formula.
- Import preserves values **verbatim**: `XCUUSD`, setup type `welcome`,
  Persian notes, and hand-typed RSI variants (`Rising From Support` vs the
  option `Rising from Support`) are never normalized. Editing a trade may keep
  its legacy unlisted RSI lines; new values must come from the Options list.

## Analytics

`GET /api/analytics` (used by the dashboard and the Excel export) recomputes
the workbook's Analytics sheet live: Overview (7 metrics), Profit & Loss (9),
Risk & Ratios (7), and four performance tables (by Symbol, Direction, Setup
Type, Mental State). Group rows are enumerated from the **Options lists**, so
unused groups appear with 0/blank exactly like the spreadsheet, and every
figure updates automatically on any change. The dashboard adds a cumulative
P&L curve, win/loss donut and P&L-by-symbol chart, and can be filtered.

## REST API (interactive docs at `/docs`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/trades` | list + search/filters/sort/pagination |
| POST | `/api/trades` | create (validated against Options) |
| GET/PATCH/DELETE | `/api/trades/{id}` | read / partial update / delete (renumbers) |
| POST | `/api/trades/{id}/duplicate` | clone (appended at end, no PnL if open) |
| POST | `/api/trades/reorder` | reorder journal (`ordered_ids`), recomputes streaks |
| GET/POST | `/api/options`, `/api/options/{list}` | the 5 dropdown lists |
| PATCH/DELETE | `/api/options/{list}/{id}` | rename / delete values |
| POST | `/api/options/{list}/reorder` | reorder a list |
| GET | `/api/analytics` | full dashboard payload (accepts same filters) |
| POST | `/api/io/import?mode=replace\|merge` | upload .xlsx (Journal [+ Options]) |
| GET | `/api/io/export/journal` | Journal .xlsx **with live formulas** |
| GET | `/api/io/export/analytics` | Analytics sheet reproduction |
| GET | `/api/io/export/backup` | pure-values backup (Journal + Options) — re-importable |

Invalid categorical values are rejected with 422 until added via Options
(the importer itself bypasses validation to preserve existing data verbatim).

## Project layout

```
backend/app
  calculations.py   pure derived-field engine (single source of truth)
  analytics.py      dashboard engine (Overview/P&L/Risk/groups/equity curve)
  importer.py       verbatim workbook import (skip Analytics, keep literals)
  exporter.py       journal (formulas) / analytics / backup exports
  models.py         trades + option_values + app_state (SQLite)
  routers/          trades, options, analytics, io
  tests/            79 pytest cases incl. real-workbook import checks
frontend_v2/        THE application frontend (v2 React UI; v1 frontend removed)
  src/api/          typed client + query keys/hooks mirroring app2 schemas
  src/pages/        Quest Hub, Trade Journal, Quick Capture, Quick/Deep Review,
                    Emotional Journal, Daily/Weekly Review, Quest Center,
                    Achievements, Settings
  src/feedback/     toast + level-up overlay (driven only by backend payloads)
  src/components/   shell, quest cards, rating pills, states, dialogs
  scripts/          capture-screenshots.mjs (`npm run screenshots`)
scripts/
  bootstrap.py            create DB + seed from workbook (v1)
  verify_against_excel.py diff live analytics vs workbook cached values (v1)
  seed_demo_v2.py         build data/tradequest_v2_demo.db for demos/screenshots
  smoke_phase3_v2.py      live end-to-end check of v2 API + built SPA (85 checks)
```

## Configuration (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `TRADEQUEST_DB` | `data/tradequest.db` | SQLite file (v1) |
| `TRADEQUEST_EXCEL` | workbook next to repo root | seed workbook path (v1 only) |
| `TRADEQUEST_CORS` | vite dev origins | comma-separated CORS list (v1) |
| `TRADEQUEST2_DB` | `data/tradequest_v2.db` | SQLite file (v2) |
| `TRADEQUEST2_CORS` | localhost origins only | CORS list (v2) |
| `TRADEQUEST2_SCREENSHOT_DIRS` | empty (fail-closed); `.bat` launchers preset `%USERPROFILE%\Pictures` | screenshot allow-list (`;`-separated, v2) |
| `TRADEQUEST2_STATIC_DIR` | `frontend_v2/dist` | built UI served by the backend when present (v2) |

---

# Trade Quest v2 (Phase 2 — backend)

A gamified, sci-fi-RPG-style journaling backend implemented in
`backend/app2/`. **Implemented (tested):** trade journal + Quick Capture,
manual close, optional manual `user_pnl`, Quick/Deep Reviews, Lessons
(3-per-review XP cap), Emotional Journal (+10 first entry per local day,
+2 each additional), Daily Review (+15/date), Weekly Review (+30/ISO week),
settings CRUD with historical-label preservation, append-only XP ledger with
idempotency keys, levels (100+50·(n−1)), 23-quest catalog with explicit claim
workflow (RF-04 "Double Take" and LQ-03 "Mentor Voice" implemented; LQ-02
deferred pending structured mistake tags), 13 achievements (2 hidden),
dashboard aggregation, local backup endpoint, and `xp_awarded`/`level_up`
feedback on creation responses for frontend integration. **Phase 3 (above) now
delivers the UI; still deferred:** LQ-02 quest condition (needs structured
mistake tags, not keyword matching), Consistency Quest reward values (user
decision pending).

## Trade Quest v2 (Phase 3 — frontend)

`frontend_v2/` is the project's frontend: a React 19 + TypeScript + Vite app
(TanStack Query, React Router, Recharts, Lucide). It is served by the v2
backend from `frontend_v2/dist` and is the only UI in the project.

```powershell
cd frontend_v2
npm install
npm run dev        # http://127.0.0.1:5174, /api proxied to 127.0.0.1:8001
npm test           # 36 Vitest/Testing-Library checks
npm run typecheck  # tsc --noEmit
npm run build      # emits frontend_v2/dist for the backend to serve
```

Sections: Quest Hub (dashboard/XP/activity), Trade Journal (server-side
status/symbol filters, paging, detail/edit/close/delete), Quick Capture,
Quick Review, Deep Review (+ lessons), Emotional Journal, Daily Review,
Weekly Review, Quest Center (explicit claim), Achievements, Settings
(symbols/setups/emotions, consistency opt-in, backups).

Every screen is pictured in **`docs/screenshots/phase3/`** (full-page captures
of the real app on the demo dataset); re-capture with
`backend\\.venv\\Scripts\\python scripts\\seed_demo_v2.py`, then start the
backend on that demo DB and run `npm run screenshots` inside `frontend_v2`.

Contract rules the UI enforces:

- XP/levels/quests/achievements are **never** computed in React; every value
  comes from a backend response.
- A toast shows XP only when `xp_awarded > 0`; the level-up overlay only when
  the response carries a real `level_up` object — query refetches never
  notify.
- Quest rewards are claimed only through `POST /api/quests/{code}/claim`;
  undecided (`reward_xp: null`) and deferred quests show no reward.
- Screenshots are displayed from `/api/trades/{id}/screenshot` only (server
  allow-list; a refusal is shown as a plain message, never bypassed).
- Locked hidden achievements stay `???` exactly as the backend reports.

## v2 security & privacy (local-first)

- Binds to `127.0.0.1` only — never `0.0.0.0`.
- No cloud sync, accounts, telemetry, broker, or market-data integration.
- XP amounts are server-side constants; no endpoint accepts an XP value.
- Screenshot paths are stored as text; the serving endpoint validates
  absolute path + image extension + file size AND that the fully resolved
  path (symlinks/junctions/traversal expanded) is inside one of the
  configured permitted directories (`TRADEQUEST2_SCREENSHOT_DIRS`).
  Unconfigured = refused (fail-closed); the `.bat` launchers preset
  `%USERPROFILE%\Pictures`.
- All data stays in `data/tradequest_v2.db` (+ `data/backups/` copies).

## v2 database & backups

- Fresh empty database created on first start; never overwritten or migrated
  from v1.
- `GET /api/system/backup` writes a timestamped SQLite-consistent copy next
  to the DB (last 10 kept).
- Full pre-Phase-2 project backup:
  `D:\trading strategy\TradeQuest_v1_backup_phase2` (rollback: copy it back
  over the project folder; v2 files live only in `backend/app2`,
  `backend/tests_v2`, and the root `.bat` scripts).


## Notes & limitations

- Long text is edited in the drawer/form (double-click cell editing covers
  short fields, dates, times and dropdowns).
- Import `replace` wipes trades+options first; `merge` appends trades and adds
  only unseen option values.
- Commissions sum to $2.20 in the imported data (matches the workbook's cached
  $2.20); swap is $0.

