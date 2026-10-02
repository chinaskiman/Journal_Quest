# Trade Quest V2 — Setup and Operations Guide

Audience: someone installing and running Trade Quest V2 on a Windows PC.
Persian user guide: [`../README_FA.md`](../README_FA.md).

**How to read this document.** Every statement is marked:

- **Verified** — confirmed by reading the code/configuration, or by a test that was
  actually executed (the command is named).
- **Inferred** — follows from the code but not exercised end-to-end.
- **Not tested** — a procedure that exists in principle but has never been run
  against a real journal database. Do not rely on it without validating it on a
  copy first.

Last reviewed: 2026-10-02 (Phase 2 dependency audit), against the current project tree.

---

## 1. What this application is

Trade Quest V2 is a single-user, local-first trading **journal** for trades you
have already taken. It rewards journaling behaviour (captures, reviews, lessons,
emotional check-ins, daily/weekly reviews, claimed quests) with XP, levels, quests
and achievements.

It is **not** a trading platform. There is no broker connection, no order entry,
no P&L calculation (P&L is entered manually and is stored verbatim), no accounts,
no cloud services, no telemetry, and no Excel import in v2. The server binds only
to `127.0.0.1`. **Verified** (static inspection of `backend/app2`).

---

## 2. System requirements

| Requirement | Status | Notes |
|---|---|---|
| Windows with `cmd.exe` and PowerShell | **Verified** | All launchers are `.bat` files; paths are resolved relative to the script (`%~dp0`) |
| **Python 3.11+** | **Verified** | Enforced by `setup_tradequest.bat` and `start_tradequest_v2.bat` since the Phase 2 audit. See §2.1 for why 3.11 |
| **Node.js 20.19+ or 22.12+** | **Verified** | Declared in `frontend_v2/package.json` `engines`. **Not** required at runtime if `frontend_v2\dist` is already built |
| npm 10+ | **Verified** | Declared in the same `engines` block (build/test tooling) |
| Internet access | **Inferred** | Needed once, during `setup_tradequest.bat` (pip + npm downloads). Not needed afterwards |
| Google Chrome or Edge | **Optional** | Only for `npm run screenshots` (`playwright-core` drives an installed browser) |
| Free TCP port 8001 | **Verified** | Hard-coded in the launchers. Port 5174 is used only by the Vite dev server |
| Disk space | **Inferred** | ~200 MB for `frontend_v2/node_modules`; < 10 MB for the database and backups |

No Windows edition or CPU requirement is expressed anywhere in the project.

### 2.1 Supported Python version — why 3.11

**Verified on:** CPython **3.14.3** (64-bit, Windows) — the interpreter in
`backend\.venv`. All suites pass on it.

The floor is **3.11**, chosen from evidence rather than convention:

- The highest floor declared by any installed dependency is **3.11**
  (`SQLAlchemy 2.1.1`, `websockets 17.1`). Everything else requires 3.9–3.10.
- The project's own code needs **3.10+**: `backend/app2/schemas.py` uses PEP 604
  unions (`str | None`) in Pydantic v2 models, and Pydantic evaluates those
  annotations at runtime rather than treating them as inert strings.
- 3.11 is therefore the highest of the binding constraints.

**The launcher checks are advisory-safe by design:** they only *report* an
unsupported version and exit non-zero. They never install, download, or upgrade
Python, and on a supported version the launchers continue exactly as before.

**Uncertainty (documented, not invented):** only 3.14.3 was actually exercised.
3.11–3.13 are justified by dependency metadata and language features but were
**not** run here. A machine on 3.11–3.13 is expected to work; treat it as
"supported by evidence", not "tested". The same applies to Node: 24.11.1 was
tested, while the declared range spans 20.19+ and 22.12+.

---

## 3. Installation (one-time)

Double-click **`setup_tradequest.bat`**. It performs, in order: **Verified**

1. Checks that `python` is on `PATH` and that it is **3.11+**. On an older
   version it prints the detected version, explains the requirement, and exits —
   it does **not** install or upgrade anything.
2. Creates `backend\.venv` if it does not exist.
3. Runs `.venv\Scripts\python.exe -m pip install --upgrade pip`.
4. Runs `.venv\Scripts\python.exe -m pip install -r requirements.txt`
   (`backend/requirements.txt`), which also pulls in `requirements-dev.txt`.
5. If `npm` exists: `npm install` in `frontend_v2`, then `npm run build`
   (which runs `tsc --noEmit && vite build`) so the backend can serve the UI.
   If `npm` is missing it prints a note and **skips** this step.

Result: the application can be started with `start_tradequest_v2.bat`. If step 5
was skipped, the app still runs but serves the JSON API only — build the UI later
with:

```powershell
cd frontend_v2
npm install
npm run build
```

### 3.1 Dependency organization (Phase 2 audit)

`backend\requirements.txt` remains the **single installation path** — existing
instructions and `setup_tradequest.bat` keep working unchanged. Internally the
dependencies are now grouped and annotated:

| File | Contents | Needed to run V2? |
|---|---|---|
| `backend\requirements.txt` | V2 runtime (`fastapi`, `uvicorn[standard]`, `sqlalchemy`, `pydantic`) **+** v1 legacy extras (`openpyxl`, `python-multipart`) **+** `-r requirements-dev.txt` | Yes — install this one file |
| `backend\requirements-dev.txt` | `pytest`, `httpx` | Only for running the test suites |
| `backend\constraints-verified.txt` | Exact versions proven to work (a *constraints* file, applied with `-c`) | Optional, for reproducible rebuilds |

**Why `openpyxl` and `python-multipart` stay in the main file even though V2 does
not use them.** A Phase 2 import audit (plus an import-blocking probe, §3.2)
confirmed they are imported only by **V1** code: `backend\app\exporter.py`,
`backend\app\importer.py`, and `backend\app\routers\io.py` (`UploadFile`). They
were **not** removed, because `backend\app` is the retained V1 rollback path and
removing them would break the V1 app and its tests. Keeping them in the single
install path preserves the current working application.

**`httpx` is a test dependency, not a runtime one** — both `conftest.py` files use
`fastapi.testclient.TestClient`, which imports it.

**Reproducible rebuild.** Version floors stay open-ended (`>=`) in
`requirements.txt`; to reproduce the exact environment this project was verified
against, add the constraints file:

```powershell
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt -c constraints-verified.txt
```

Pinning alone does **not** make an install reproducible — the constraints file only
records what was already tested, and a fresh `pip install` may still resolve newer
versions of anything not listed there.

### 3.2 How the "V2 does not need openpyxl / python-multipart" claim was verified

**Verified** by blocking those two modules at import time (`sys.meta_path`
hook raising `ModuleNotFoundError`) and then starting the real app against a
**throw-away** database in `%TEMP%`:

- `app2.main` imported successfully and Starlette degraded its multipart support
  to `None` (it imports `python_multipart` inside a `try/except`, so a missing
  package is tolerated).
- The v2 API answered normally: `/api/system/health`, `/api/trades`,
  `/api/quests`, `/api/achievements`, `/api/levels`, `/api/dashboard`, `/api/xp`
  all returned `200`.
- The OpenAPI schema confirms V2 exposes **no** `multipart/form-data` or
  `UploadFile` endpoint, so no request path requires the multipart parser.
- The probe used a temporary database only. **No real journal database was
  opened, and both real databases are byte-identical before and after.**

The temporary database and all probe scripts were deleted afterwards.

---

## 4. Running the application

1. Double-click **`start_tradequest_v2.bat`**. A console window opens showing
   `Starting Trade Quest v2 backend on http://127.0.0.1:8001 ...`. **Verified**
2. Open **`http://127.0.0.1:8001`** in your browser. The launcher does **not**
   open a browser for you. **Verified**
3. Press `Ctrl+C` in the console window to stop the server. **Verified**

The same port serves both the built UI and the API; API documentation is at
`http://127.0.0.1:8001/docs` (loopback only, no authentication). **Verified**

**Development mode (optional).** Run `start_backend_v2_dev.bat` in one window
(uvicorn with `--reload`) and `start_frontend_v2_dev.bat` in another (Vite dev
server on `http://127.0.0.1:5174`, proxying `/api` to `127.0.0.1:8001`). **Verified**

### 4.1 Where data lives — development vs. future packaged version

The application resolves two different roots, and only one of them is writable.
This matters because a frozen (packaged) build runs from a **temporary
extraction folder** that must never receive your journal.

| | Development (current, `.bat`) | Future packaged ("frozen") mode |
|---|---|---|
| How it is detected | `sys.frozen` is false | `sys.frozen` is true |
| Code + Python runtime | `backend\.venv` | the bundle / installer folder |
| Frontend `dist` (read-only) | `<project>\frontend_v2\dist` | `<bundle>\frontend_v2\dist` |
| **Database + backups (writable)** | `<project>\data\` | `%LOCALAPPDATA%\TradeQuest\` |
| Working directory used for assets | no | **no** — resolved from `sys._MEIPASS` |

In development **nothing changes**: data stays in `<project>\data\`, exactly as
before. **Verified** by comparing the resolved paths before and after the Phase A
change, and by `backend/tests_v2/test_paths.py`.

In the future packaged version, user data would live in:

```
%LOCALAPPDATA%\TradeQuest\
    tradequest_v2.db        ← your journal
    backups\                ← automatic backups (10 newest kept)
```

`%LOCALAPPDATA%` is per-user, writable without administrator rights, and is
**not** inside the installer folder or the extraction folder, so uninstalling or
upgrading the program cannot take your journal with it.

**If `LOCALAPPDATA` is missing or invalid, startup stops with a clear error**
instead of silently writing to a temporary folder that would be deleted later.
Two supported ways out of that situation:

- set `LOCALAPPDATA` to a valid writable folder, **or**
- set `TRADEQUEST2_DB` to an explicit absolute database path.

**Environment overrides in frozen mode.** All existing overrides keep working;
only the *default* locations change:

| Variable | Frozen-mode behaviour |
|---|---|
| `TRADEQUEST2_DB` | Still wins over `%LOCALAPPDATA%`; backups follow it |
| `TRADEQUEST2_DB_URL` | Still wins; note it does **not** relocate the backups |
| `TRADEQUEST2_STATIC_DIR` | Still wins over the bundled `dist` |
| `TRADEQUEST2_SCREENSHOT_DIRS` | Unchanged — still read per request, still fail-closed when empty |
| `TRADEQUEST2_CORS` | Unchanged; irrelevant in production (same origin) |
| `TRADEQUEST2_PORT` | **No effect** — the port is hard-coded in the launchers (see §6) |

> **Status:** the standalone executable **has not been built or validated**. Only
> the path-resolution logic is in place and covered by tests. There is no
> installer, no desktop window, and no single-instance lock yet.

---

### 4.2 Streak Break & Recovery (user-facing rules)

Streak tracking is **enabled by default** and can be switched off in
`Settings → Options`. A broken streak never removes XP, quests or badges.

**What counts as an active day.** A *local calendar day* on which you completed at
least one of: Daily Review, Weekly Review, Quick Review, Deep Review, a Lesson,
or an Emotional Journal entry. Trade capture, trade opening/closing, edits,
P&L changes and duplicate submissions **never** count, and a day counts at most
once. Streak days themselves award **0 XP** — there is no daily bonus, no
multiplier and no penalty.

**Minimum streak.** A break is only eligible when the previous run reached **3
consecutive active days**.

**Yesterday-grace.** `current_streak` covers consecutive active days ending
today **or** yesterday. Missing only today does not break anything: a break is
considered only once today *and* yesterday are both inactive, so nothing is
declared at midnight or after a single missed day.

**Detection date.** The break is recorded on the day it is noticed. Two database
UNIQUE constraints make it idempotent — `detected_on` (one break per day) and
`broke_on` (the same historical gap is never re-processed on a later day).

**RC-01 — Reflection Quest (+25 XP).** Activated by an eligible break. Two short,
optional, habit-focused prompts: *what got in the way of your journaling
routine?* and *what is one small thing that could help you resume?* Nothing about
losses, trade size or trading frequency is ever asked. Saving it completes the
quest for that event; XP is granted only through the normal `Claim reward`
action, **once per streak-break event**.

**RC-02 — Recovery Quest (+50 XP).** Completes after **2 distinct qualifying
active local days** on or after the break date. Only the six activities above
count; trade activity never does, and there is no daily requirement. Claimable
**once per streak-break event**.

**ACH-REC-PHOENIX — "Rising Phoenix"** (hidden, `secret`). Unlocks only once both
quests are complete. Because `achievement_unlocks.code` is the primary key it can
be unlocked **once globally**; `seen_at` remains mutable exactly like the
existing achievements.

**Disabling / re-enabling.** Disabling stops new detection, quests, XP and badge
unlocks from this feature, and preserves every existing event, reflection, quest
completion, XP entry and achievement unlock. Re-enabling establishes a **new
activation baseline from that day**, so no break is ever generated retroactively
for the disabled period. The baseline is persisted, so restarts never move the
starting point.

**Historical backfill.** None. Activity before the activation date cannot seed a
streak and cannot produce a retroactive break; no historical record is rewritten.

**Timezone handling and limitation.** `created_at` is stored as naive **UTC**
(`server_default=func.now()`), while other app timestamps are naive local.
Explicit local-date columns are preferred (`DailyReview.review_date`,
`EmotionalEntry.local_date`); Weekly Review, Quick Review, Deep Review and Lesson
have no such column, so their `created_at` is explicitly converted from UTC to
local and is **never** read as local wall-clock — an activity at 00:30 local is
filed on the correct day. **Limitation:** the database stores no timezone
identifier, so the *server's current* timezone is used; if the machine's timezone
changes, day attribution of older UTC timestamps can shift. Nothing is rewritten.

**Multiple independent events — rewards are per-event.** Each break gets its own
`streak_events` row with its own reflection/recovery state, and RC-01 / RC-02 are
**per-event quests**: every eligible break can claim the reward again, so a later
independent break earns a fresh +25 / +50. Each award is recorded against a
`streak_quest_claims` row and an XP ledger key of `streak:{event_id}:{quest_code}`,
protected by `UNIQUE(event_id, quest_code)` and the ledger's own UNIQUE
idempotency key. Claiming when nothing is pending returns `409` and awards
nothing. Every other quest keeps the original once-per-quest behaviour
(`quest:{version}:{code}` key and a single `claimed_at`).

---

### 4.3 Experimental frozen build (Phase B spike)

> **Status: experimental executable — NOT an installer.** There is no setup
> wizard, no Start Menu entry, no uninstaller and no auto-updater. Phase C
> (desktop shell) and Phase D (installer) have not been started.

**Prerequisites:** Windows x64, Python 3.11+ (built and tested on **3.14.3**),
Node.js/npm for the frontend build only. A disposable build virtual environment
holding PyInstaller.

**Build (reproducible, from the project root):**

```powershell
# 1. disposable build venv - backend\.venv is NOT modified
python -m venv .buildvenv
.buildvenv\Scripts\python -m pip install -r backend\requirements.txt `
                                      -c backend\constraints-verified.txt
.buildvenv\Scripts\python -m pip install pyinstaller==6.22.3

# 2. build the SPA (must exist before bundling)
cd frontend_v2; npm install; npm run build; cd ..

# 3. build --onedir (never --onefile)
.buildvenv\Scripts\python -m PyInstaller --noconfirm --clean `
    --distpath dist --workpath build packaging\TradeQuest.spec
```

**Output structure**

```
dist\TradeQuest\
    TradeQuest.exe                        ← the executable (~9 MB)
    _internal\
        frontend_v2\dist\                 ← bundled SPA (read-only assets)
        *.dll, base_library.zip, ...      ← Python + dependencies
```

**Launch:** double-click `dist\TradeQuest\TradeQuest.exe`, or run it from any
directory. It prints its resolved mode, host, data directory and static
directory, then serves the UI at `http://127.0.0.1:8001`. **It does not open a
browser by itself** — open the URL manually.

**How to tell the two modes apart**

| | Development | Frozen (packaged) |
|---|---|---|
| Startup line | `Starting Trade Quest v2 backend on…` | `[Trade Quest] mode : frozen` |
| Database | `<project>\data\tradequest_v2.db` | `%LOCALAPPDATA%\TradeQuest\tradequest_v2.db` |
| Frontend assets | `<project>\frontend_v2\dist` | `<bundle>\_internal\frontend_v2\dist` |

**Verified on 2026-10-02** (Windows 10 Pro 19045 x64, Python 3.14.3): the
executable started from `C:\Windows` (i.e. with an unrelated working directory),
reported `frozen` mode, bound **only** to `127.0.0.1:8001`, answered
`/api/system/health` and `/` with `200`, served both hashed SPA assets, accepted
an API write (20 XP), created its database **only** under the test
`%LOCALAPPDATA%`, contained zero database files, restarted with all data intact,
and exited leaving no orphan process. Regression suites unchanged: 226 v2 backend,
79 v1 backend, 59 frontend tests, typecheck clean, frontend build OK.

**Known limitations**

- **Not tested on a clean Windows machine.** The executable has only been run on
  this development host, which already has Python and Node.js installed.
  Compatibility with a machine without them is an *expectation*, not a verified
  result.
- **Antivirus false positives are likely but unmeasured.** The bootloader may be
  flagged; `--onedir` (no `--onefile`, no UPX) is the documented mitigation.
- **No single-instance protection** — two launches will collide on port 8001.
- **Not code-signed**, so SmartScreen may warn on first run.
- **Shutdown was verified by process termination** (`taskkill`), not by a real
  Ctrl+C in an interactive console; uvicorn's graceful lifespan shutdown was
  therefore not exercised through the UI.
- The build is not yet reproducible across machines in a cryptographic sense;
  PyInstaller's bootloader version must stay pinned.

### 4.4 Experimental desktop window (Phase C spike)

> **Status: experimental desktop shell — STILL NOT an installer.** No setup
> wizard, no Start Menu entry, no uninstaller, no auto-updater. Phase D has not
> been started.

**What it is:** the same V2 backend from §4.3, plus a native `pywebview` window
(WebView2 backend) that loads the very same bundled React SPA. There is no
separate frontend and no Python↔JS bridge — the SPA talks to the local HTTP API
exactly as it does in a browser.

**Windows runtime prerequisites**

| Requirement | Why | Status on the test host |
|---|---|---|
| **Edge WebView2 Runtime** | pywebview's Windows renderer | **present — 154.0.4258.48** |
| **.NET Framework 4.x** | `pythonnet` interop (pulled in by pywebview on Windows) | **present** (v4.0.30319) |

**Build** (build venv now also needs pywebview; runtime requirements unchanged):

```powershell
.buildvenv\Scripts\python -m pip install pywebview==6.2.1   # pulls pythonnet
.buildvenv\Scripts\python -m PyInstaller --noconfirm --clean `
    --distpath dist-desktop --workpath build-desktop ^
    packaging\TradeQuestDesktop.spec
```

The desktop spec additionally bundles the native payloads static analysis would
miss: `pythonnet/runtime/Python.Runtime.dll`, `clr_loader/.../ClrLoader.dll`
and `webview/lib/runtimes/win-*/native/WebView2Loader.dll`. The WebView2
**runtime** is not bundled — the machine's Evergreen runtime is used.

**Launch:** run `dist-desktop\TradeQuest\TradeQuest.exe`. A "Trade Quest" window
(1280×860, resizable) opens. Startup prints:

```
[Trade Quest] mode      : frozen desktop
[Trade Quest] host      : 127.0.0.1
[Trade Quest] data dir  : %LOCALAPPDATA%\TradeQuest
[Trade Quest] backend ready at http://127.0.0.1:8001
```

**Startup/shutdown behaviour (verified 2026-10-02)**

- The backend is started in a background thread and the window is only navigated
  to it **after** `/api/system/health` answers, so a blank window is never shown.
- Readiness is a real HTTP poll with a 30 s bound — not a fixed sleep.
- **Closing the window shuts the backend down.** Verified by posting `WM_CLOSE`
  to the window: the log printed `[Trade Quest] backend stopped.`, the process
  exited, no child/orphan remained and port 8001 was released.
- **A second launch fails gracefully**: the port guard reports "Trade Quest is
  already running (port 8001 is in use)", no second window opens. This is
  port-conflict detection only, not an IPC/PID scheme; a small race between the
  probe and Uvicorn binding remains possible.
- **Startup failures are reported, not silent**: an invalid `%LOCALAPPDATA%`
  prints `Could not load application configuration` with the traceback and exits
  instead of opening a blank window.

**Known limitations**

- **Not tested on a clean Windows machine.** Verified only on this development
  host (which has Python/Node installed). Compatibility with a machine lacking
  them is an **expectation, not a verified result**. In particular the WebView2
  Runtime and .NET Framework were already present here, so the installer-less
  path on a bare machine is untested.
- Antivirus false positives remain **unmeasured**.
- Not code-signed → SmartScreen may warn.
- Errors are shown in a native MessageBox **and** the console; a windowed build
  (`console=False`) is not used yet, so a console window is also visible.
- `pywebview` 6.2.1 advertises support only up to Python 3.13 in its classifiers;
  it ran fine on 3.14.3 here, but that combination is newer than its metadata.

### 4.5 Windows installer (Phase D)

> **Experimental.** Not code-signed, not an auto-updater, no in-app updater.

**Installer file**

| | |
|---|---|
| Filename | `TradeQuest-2.0.0-win-x64-setup.exe` |
| Built to | `dist-installer\` |
| Size | 19,954,539 bytes (19.0 MB) |
| Tool | **Inno Setup 7.1.0 (x64)** — `ISCC.exe` |
| Payload | the Phase C bundle `dist-desktop\TradeQuest\` (110 files, 37.3 MB) |

**Build command** (from the project root)

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe" /Q packaging\TradeQuest.iss
```

**Install location & shortcuts**

- Installs **per-machine** to `%ProgramFiles%\Trade Quest` (requires
  administrator rights; the installer states this — no silent surprise elevation).
- Start Menu group **Trade Quest** with *Trade Quest* and *Uninstall Trade Quest*.
- Desktop shortcut is an **optional, unchecked-by-default task**, so the user
  chooses.
- All shortcuts point at `{app}\TradeQuest.exe` with `WorkingDir` set to `{app}`;
  frozen asset and data paths are absolute, so the working directory is never
  relied upon.

**User data is never touched by the installer** — verified: after a full
install → use → **uninstall** cycle the journal and its backup were still present
and readable (`trades=1, xp_events=1, symbols=1`).

| Location | Contents |
|---|---|
| `%ProgramFiles%\Trade Quest\` | application files only (read-only in practice) |
| `%LOCALAPPDATA%\TradeQuest\` | `tradequest_v2.db`, `-wal`, `-shm`, `backups\` |

The `[UninstallDelete]` section deliberately targets **only** `{app}`; there is
no entry for the data directory, and no data-wipe option exists.

**Runtime prerequisites (verified on the test host)**

- **Microsoft Edge WebView2 Runtime** — the installer **detects** it by reading
  the EdgeUpdate registry key and, if absent, shows a message telling the user
  what to install. It never downloads it and has no installer-time network use.
- **.NET Framework 4.x** — required by `pythonnet` (pywebview's Windows backend).

**Update / reinstall**

Reinstalling the same version over an existing install succeeds (exit 0), does
**not** duplicate shortcuts, and does not touch user data: a relaunch afterwards
still showed the original trade, XP and quest state.

> **Not tested:** a genuine *upgrade* between two different builds. Only one build
> exists, so this was a reinstall of the same version — not a full upgrade test.

**Uninstall**

Removes the application directory, both shortcuts and the Add/Remove Programs
entry, and leaves `%LOCALAPPDATA%\TradeQuest` and its backups intact.

---

## 5. Where your data lives

| Item | Location | Notes |
|---|---|---|
| Journal database | `data\tradequest_v2.db` | SQLite (WAL mode). Created empty on first start; the console prints `[tradequest-v2] created fresh empty database` |
| SQLite side files | `data\tradequest_v2.db-wal`, `…-shm` | Transient while the app runs; normal to see them |
| Backups | `data\backups\tradequest_v2_*.db` | Created by the app (see §7) |
| Demo database | `data\tradequest_v2_demo.db` | Optional sample data; created by `scripts\seed_demo_v2.py` |
| v1 database (retained) | `data\tradequest.db` | Belongs to the older v1 backend; v2 never reads or writes it |

Verified facts: a fresh install creates a new empty database
(`backend/app2/db.py:50-60` uses `create_all` and never drops data); v2 contains
no importer, migration or seeding from v1; `data\` and `data\backups\` are created
if missing (`backend/app2/config.py:36,49`).

**Your data is only the `data\tradequest_v2.db` file (plus its backups).** To move
or protect your journal, copy that folder while the app is closed.

**Deleting a trade** is a soft delete in the UI: the row is flagged with
`deleted_at` and disappears from the journal, while the XP it earned stays in the
ledger (no clawback). Permanent deletion exists only as an API option
(`DELETE /api/trades/{id}?hard=true`), which the UI never sends. **Verified**.

---

## 6. Configuration

All configuration is done with **environment variables set before launching** —
there is no configuration file and no settings UI for infrastructure options.

> **The `.env` file in the project root is NOT read by the application.**
> **Verified**: no `dotenv`/`load_dotenv` call exists anywhere in `backend/app2`,
> and `python-dotenv` is not in `requirements.txt`. The current `.env` is a v1-era
> template. Set variables in your shell, or define them above the launcher call.

### 6.1 Variables the code actually reads

| Variable | Default | Purpose |
|---|---|---|
| `TRADEQUEST2_DB` | `data\tradequest_v2.db` | Path to the SQLite file. Its parent directory is also where backups are written (`BACKUP_DIR = DB_PATH.parent / "backups"`). This is the safe way to point the app at a different journal |
| `TRADEQUEST2_DB_URL` | `sqlite:///<TRADEQUEST2_DB>` | Full SQLAlchemy connection URL, overriding the SQLite path |
| `TRADEQUEST2_CORS` | localhost origins (5173, 5174, 4173, 8001) | Comma-separated allowed CORS origins |
| `TRADEQUEST2_SCREENSHOT_DIRS` | empty (**fail-closed**) | `;`-separated directories the screenshot endpoint may read from. The launchers preset it to `%USERPROFILE%\Pictures` when undefined |
| `TRADEQUEST2_STATIC_DIR` | `frontend_v2\dist` | Directory of the built UI the backend serves; if absent the API runs alone |

### 6.2 `TRADEQUEST2_DB_URL` — what is verified and what is not

**Verified:** `backend/app2/config.py:44` reads it and uses it verbatim as the
SQLAlchemy URL; when unset, the app builds `sqlite:///<DB_PATH>`.

**Inferred (and the reason to be careful):** the rest of the configuration still
derives from the *path* variables, not from the URL:

- `DB_PATH` (used by the "is this a fresh database?" check) and `BACKUP_DIR`
  (where backups are written) are computed from `TRADEQUEST2_DB` or the default
  `data\tradequest_v2.db` — **not** from `TRADEQUEST2_DB_URL`.

**Practical guidance:** prefer `TRADEQUEST2_DB` for any file relocation. Use
`TRADEQUEST2_DB_URL` only if you know exactly what you are doing, and expect the
fresh-database message and the backup location to keep referring to the
*path*-based location. This behaviour was **not** exercised end-to-end here.

### 6.3 `TRADEQUEST2_PORT` is documented but not implemented

`backend/app2/config.py:12` documents `TRADEQUEST2_PORT`, but no code reads it: the
launchers pass `--port 8001` explicitly and `app2/main.py:99` hard-codes `8001`.
**Verified** by searching all of `backend/app2`. Setting it has no effect; to use
another port, edit the launcher or start uvicorn yourself.

### 6.4 Examples

```powershell
# Use a different journal file (backups follow it automatically)
$env:TRADEQUEST2_DB="D:\Journals\tradequest_v2.db"
start_tradequest_v2.bat

# Allow screenshots from two folders
$env:TRADEQUEST2_SCREENSHOT_DIRS="C:\Users\me\Pictures;D:\TradeCharts"
start_tradequest_v2.bat
```

---

## 7. Backup (verified)

**Create a backup from the UI (recommended):** `Settings → Options → Backups →
Create backup now`. A toast confirms the file name. **Verified**

What happens (verified by code inspection):

- A timestamped copy is written to `data\backups\`, e.g.
  `tradequest_v2_20261001_195726.db`.
- The copy uses SQLite's online backup API, so it is consistent even while the
  app is running.
- Only the **10 most recent** backups are kept; older ones are deleted
  (`MAX_BACKUPS = 10`).
- Copy any backup you care about to a safe place immediately — the retention
  policy will eventually delete it.
- Stored backups can be listed with `GET /api/system/backups`, and a backup can be
  created directly with `GET /api/system/backup`. **Verified** (both are exercised
  by the live smoke script `scripts\smoke_phase3_v2.py` against a running server).

**Recommended rhythm:** create a backup before any risky action (bulk edits, an
update, a manual restore experiment) and keep at least one copy outside the
project folder.

---

## 8. Restore — NOT a tested procedure

**Verified:** the application has **no restore feature** — no button, no endpoint,
no code path that writes a database file from a backup. The only database-writing
endpoint is the backup creator.

**Not tested:** the manual procedure below has never been run against a real
journal database in this project. It is a *proposal* based on how SQLite handles
file replacement. **Validate it on a copy first; never make it your first
experiment on your only journal.**

Proposed steps (validate on a copy first):

1. Stop the application (`Ctrl+C`).
2. Copy the current `data\tradequest_v2.db` somewhere safe as a pre-restore copy.
3. If `tradequest_v2.db-wal` / `tradequest_v2.db-shm` still exist, delete them so
   stale WAL content cannot be merged into the restored file.
4. Copy the chosen `data\backups\tradequest_v2_*.db` over
   `data\tradequest_v2.db`.
5. Start the app and sanity-check: `Quest Hub` (level/XP) and `Trade Journal`
   (trade count) should match the restored point in time.

**Recommendation for a future, separately approved task:** add a documented,
tested restore script that (a) refuses to run unless the app is stopped, (b) makes
a pre-restore copy automatically, and (c) is covered by an automated test against
a temporary database. Until then, treat restore as manual and unverified.

---

## 9. Troubleshooting (based on verified behaviour)

| Symptom | Cause | What to do |
|---|---|---|
| `[ERROR] Python virtual environment not found` | `setup_tradequest.bat` was never run | Run it once, then launch again |
| `Backend unreachable` banner in the UI | The API is not running, or the UI is served by a different process | Start `start_tradequest_v2.bat`; in dev mode make sure the backend window runs first |
| The page shows JSON or `{"detail":"Not Found"}` instead of the UI | `frontend_v2\dist` is missing — the app is in API-only mode | `cd frontend_v2; npm install; npm run build` |
| Port 8001 already in use | Another copy of the app (or another program) holds the port | Close it, or change the `--port` value in the launcher |
| A screenshot shows a refusal message | The image is outside `TRADEQUEST2_SCREENSHOT_DIRS`, is not an allowed image type, is larger than 25 MB, or the allow-list is empty | Put the image in an allowed folder (the launchers preset `%USERPROFILE%\Pictures`) and store an absolute path |
| Emotional entry rejected — *not in Settings* | The emotion has not been defined | Add it under `Settings → Emotions` first |
| Trade rejected — symbol/setup not in the list | Same reason, for symbols or setups | Add the item in `Settings` first |
| Weekly Review rejects the week value | The field expects an ISO week such as `2026-W40` | Use the ISO week format |
| Everything looks empty although you already have a journal | The app is pointed at a different database | Check whether `TRADEQUEST2_DB` / `TRADEQUEST2_DB_URL` is set in your shell |
| `npm` not found | Node.js is not installed | Install Node.js 20.19+ or 22.12+ (see §2), then perform the frontend build in §3 |
| `[ERROR] Unsupported Python version` | Python on `PATH` is older than 3.11 | Install Python 3.11+ and re-run `setup_tradequest.bat`; the script never installs Python for you |
| Dev server on 5174 shows API errors | Vite proxies to `127.0.0.1:8001`; the backend is not running | Start `start_backend_v2_dev.bat` first |
| An achievement toast did not appear | Newly unlocked achievements are only announced once, while the page is open | Reload `Achievements`; the gallery always shows the true state |
| An XP toast did not appear | The server awarded 0 XP (e.g. a repeated daily review, or a lesson beyond the 3-lesson cap) | This is correct behaviour; check the totals in `Quest Hub` |
| Quests show `Reward undecided` / `Not yet available` | Consistency-quest rewards are still undefined and `LQ-02` is deferred | Nothing to fix — see §12 |

---

## 10. Safe update procedure (preserve your journal)

The journal lives entirely in `data\tradequest_v2.db` plus `data\backups\`.

1. Close the app (`Ctrl+C`) and confirm no `python.exe` from `backend\.venv` is
   running.
2. Create a backup — either via `Settings → Backups` (preferred) or by copying
   `data\` to another location.
3. Copy the whole project to a new folder, or extract the new release **beside**
   the existing one. Keep `data\` intact; never delete or overwrite `data\` with a
   version that comes from an archive.
4. If the source contains `tradequest_v2.db-wal` or `-shm` files while the app was
   closed, they can be deleted — they are temporary SQLite files.
5. Start the new version and check `Quest Hub`, `Trade Journal` and
   `Achievements` for plausible values.
6. If something looks wrong, stop the app and restore the previous folder
   (including its `data\`).

**Verified constraint:** v2 never drops or recreates an existing database
(`create_all` only adds missing tables), and no code path outside the backup
creator writes to the database file. **Inferred:** therefore a future release can
*read* your existing file but might not be able to read a file created by a much
newer release — keep the folder of the version you actually use.
---

## 11. Verification and tests

How the currently documented behaviour was verified, and how to re-run it.

### 11.1 Automated tests

**Backend — v2 (141 tests):**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests_v2 -q
```

Coverage: levels/XP (44), quests (21), trades (14), API surface (14),
XP-toast feedback (9), database creation & first run (8), reviews (8),
achievements (6), check-ins (5), static SPA serving (2).
`backend/tests_v2/conftest.py` redirects the engine to a **temporary** database,
so the real `data\tradequest_v2.db` is never used. **Verified** by hashing the
live file before and after a run.

**Backend — v1 (79 tests), unaffected by v2:**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

`run_tests.bat` runs both suites together plus the UI tests.

**Frontend (Node required) — 51 tests in 10 files:**

```powershell
cd frontend_v2
npm test          # = vitest run, jsdom, no browser download, no server
```

`playwright-core` is a dev dependency used only by `npm run screenshots`
(driving an installed Chrome/Edge); it is not a test runner here.

**Live end-to-end check (requires the running server):**

```powershell
backend\.venv\Scripts\python.exe scripts\smoke_phase3_v2.py
```

**Verified on 2026-10-02 (Phase 2 re-run, after the dependency changes):**
`pytest backend\tests_v2` → **226 passed**; `pytest backend\tests` → **79 passed**;
`npm test` → `Test Files 11 passed (11) / Tests 59 passed (59)`;
`npm run typecheck` (`tsc --noEmit`) → **clean**; `npm run build` → **success**.
The SHA-256 of both `data\tradequest_v2.db` and `data\tradequest.db` was
identical before and after. **Verified** (commands executed).

### 11.1.1 Dependency and runtime checks (Phase 2)

```powershell
# Declared Python packages resolve to no changes (proves the split is safe)
cd backend
.venv\Scripts\python.exe -m pip install --dry-run -r requirements.txt
.venv\Scripts\python.exe -m pip install --dry-run -r requirements.txt -c constraints-verified.txt

# Interpreter actually in use
.venv\Scripts\python.exe --version     # Python 3.14.3
node --version                          # v24.11.1
npm --version                           # 11.6.2
```

Results: both dry runs reported `Requirement already satisfied` for every package
(no upgrades, no conflicts). The launcher version gates were exercised on both
paths — a supported interpreter continues to launch, and an unsupported one
prints the version, explains the requirement, and exits with code 1.

### 11.2 Manual acceptance path

Run through this once after installation (see the Persian guide for the
screenshot labels):

1. `Setup` → add a symbol, a setup and two emotions.
2. `Quick Capture` → create a trade; confirm the XP toast (+20).
3. `Quick Review` on that trade (+15); repeat the same review and confirm no
   second toast.
4. `Deep Review` (+30) and add four lessons — the UI must state that XP is capped
   at three lessons (+10 each).
5. `Emotional Journal` → add three entries on the same local day (+10, then +2,
   then +2).
6. `Daily Review` for today (+15) and `Weekly Review` for the current ISO week
   (+30).
7. `Quest Center` → `Claim reward` on a finished quest; claim twice and confirm the
   second attempt is refused without a reward.
8. `Settings → Options → Backups` → `Create backup now`; confirm the file appears
   in `data\backups\`.
9. Quit the app and confirm `data\tradequest_v2.db` still exists and the app shows
   the same level, XP and trade count after a restart.

### 11.3 Documentation-only checks

- Both guides exist: `README_FA.md`, `docs/SETUP_AND_OPERATIONS.md`.
- This guide links to the Persian guide and vice versa.
- A scan for stale variables (`TRADEQUEST2_PORT` used as if it worked, `.env`
  described as auto-loaded, restore described as a working feature) returns no
  misleading statements.

---

## 12. Verified vs. unverified summary

| Area | Status |
|---|---|
| Local install and start on Windows | **Verified** (launcher output, `/api/health`, port 8001) |
| Data location and automatic creation of an empty database | **Verified** |
| XP values, level formula `100 + 50 × (n−1)`, quest claim-once | **Verified** (API tests) |
| Backup creation, file location, 10-file retention | **Verified** (smoke script + code) |
| Screenshot allow-list is fail-closed | **Verified** (code + tests) |
| `.env` is not loaded | **Verified** (code + dependency list) |
| `TRADEQUEST2_PORT` has no effect | **Verified** (code search) |
| Python 3.11+ floor (dependency metadata + PEP 604 in Pydantic models) | **Verified** (dependency `Requires-Python` + launcher gate tested both ways) |
| Python 3.14.3 (the interpreter actually exercised) | **Verified** (all 271 tests + build) |
| Python 3.11–3.13 compatibility | **Inferred** — justified by metadata, **not executed** |
| Node `engines` range `^20.19.0 \|\| >=22.12.0` | **Verified** against `package-lock.json` (no dependency requires Node ≥22); only Node 24.11.1 executed |
| npm 10+ floor | **Inferred** (npm 11.6.2 used; no lockfile-level constraint found) |
| V2 does not import `openpyxl` / `python-multipart` | **Verified** (import-blocking probe against a temp DB; V2 has no multipart endpoint) |
| Streak day → local date via UTC conversion for `created_at`-only activities | **Verified** (unit test: 21:30 UTC → next local day) |
| Streak break idempotency (restart / repeat requests) | **Verified** (213-test suite; UNIQUE `broke_on` + `detected_on`) |
| RC-01 / RC-02 reward = 25 / 50 **per streak-break event**, streak days = 0 XP, no negative entries | **Verified** (API tests: two independent events each claim their own rewards; duplicates 409) |
| Re-enabling produces no retroactive break | **Verified** (baseline test) |
| Timezone conversion uses the *server's current* zone (no stored zone id) | **Known limitation** — documented in §4.2, not a defect |
| `requirements.txt` split preserves the resolved package set | **Verified** (`pip install --dry-run` → all "already satisfied") |
| Exact rebuild via `constraints-verified.txt` | **Verified** as a *file*; a truly clean-room rebuild on another machine is **Not tested** |
| `npm audit` reports 2 moderate advisories in `vitest` / `@vitest/mocker` (pre-existing) | **Known**, dev-only, not remediated here |
| Behaviour of `TRADEQUEST2_DB_URL` with a non-default location for backups | **Inferred**, not exercised |
| Restore from a backup | **Not tested**, not implemented in the app |
| Excel import in v2 | **Not available** (only in v1; no v2 route exists) |

---

## 13. Project layout (for operators)

| Path | Role |
|---|---|
| `start_tradequest_v2.bat` | Normal launch: API + built UI on 8001 |
| `start_backend_v2_dev.bat` / `start_frontend_v2_dev.bat` | Development launch (reload / Vite) |
| `setup_tradequest.bat` | One-time dependency installation |
| `backend\app2\` | V2 backend (config, db, routers, services) |
| `backend\tests_v2\` | V2 API/service test suite (141 tests, temporary database) |
| `backend\requirements.txt` | Install path: V2 runtime + v1 legacy extras + dev tools |
| `backend\requirements-dev.txt` | `pytest`, `httpx` (test tooling only) |
| `backend\constraints-verified.txt` | Exact versions verified in this phase (`pip install -c`) |
| `frontend_v2\` | V2 UI source; `dist\` is served by the backend |
| `data\tradequest_v2.db` | **Your journal** |
| `data\backups\` | Automatic backups (10 newest) |
| `docs\ARCHITECTURE_V2.md`, `docs\UI_V2_PLAN.md` | Technical/plan documents |
| `README_FA.md` | Persian user guide |
