"""Trade Quest v2 - application configuration.

Trade Quest is a strictly local-first, single-user application.  The backend
must always bind to 127.0.0.1 and must never be exposed publicly.

Environment overrides (all optional):

  TRADEQUEST2_DB    - SQLite database file used by the v2 app
                      (default: <project>/data/tradequest_v2.db; deliberately
                       a *different* file from the v1 database so the legacy
                       app and its data are never touched)
  TRADEQUEST2_PORT  - TCP port for the launch scripts (default 8001)
  TRADEQUEST2_CORS  - comma separated list of allowed CORS origins
                       (defaults to the local dev servers only)
  TRADEQUEST2_SCREENSHOT_DIRS - os-pathsep-separated list (on Windows ';')
                       of directories the screenshot endpoint may serve
                       files from.  Empty (default) = NO directory is
                       permitted and the endpoint refuses with 422; the
                       launch scripts preset it to %%USERPROFILE%%\\Pictures.
  TRADEQUEST2_STATIC_DIR - directory holding the built frontend_v2 SPA
                       (default: <project>/frontend_v2/dist in development,
                        <bundle>/frontend_v2/dist when frozen).  When present,
                       the app serves it locally (single-port launch at
                       http://127.0.0.1:8001); when absent, the JSON API is
                       served alone (frontend dev-server mode).

Frozen (packaged) mode
----------------------
When the app runs from a PyInstaller bundle (``sys.frozen`` is true) the
process executes from a read-only extraction directory (``sys._MEIPASS``).
Two different roots therefore have to be resolved:

  * bundle/static assets -> ``sys._MEIPASS`` (read-only, bundled)
  * writable data (database, backups) -> a stable per-user directory,
    ``%LOCALAPPDATA%\\TradeQuest``, so data is NEVER written inside the
    extraction directory or the installation directory, both of which are
    temporary/disposable.

All of ``TRADEQUEST2_DB``, ``TRADEQUEST2_DB_URL``, ``TRADEQUEST2_CORS`` and
``TRADEQUEST2_SCREENSHOT_DIRS`` keep working in both modes; only the *defaults*
change when frozen.  ``HOST`` is always ``127.0.0.1`` in both modes.

"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

# backend/app2/config.py -> parents[2] is the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Application data directory name under %LOCALAPPDATA% (frozen mode only).
APP_DIR_NAME = "TradeQuest"


class ConfigError(RuntimeError):
    """Raised when a safe path cannot be determined.

    Deliberately fatal and explicit: the app must never silently fall back to a
    temporary extraction directory, because that would scatter (or eventually
    lose) the user's journal.
    """


def is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) frozen bundle."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path | None:
    """Read-only directory holding bundled assets, or None when not frozen.

    PyInstaller extracts a one-dir/one-file bundle to ``sys._MEIPASS``; that
    directory is disposable and must never receive writable data.
    """
    if not is_frozen():
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    # Defensive fallback: a frozen build without _MEIPASS still has a known
    # executable location. Read-only either way.
    return Path(sys.executable).resolve().parent


def user_data_dir() -> Path:
    """Stable, writable, per-user data directory for frozen mode.

    ``%LOCALAPPDATA%\\TradeQuest``.  Chosen because it is per-user, writable
    without elevation, stable across upgrades, and outside both the installer
    directory and the bundle extraction directory.
    """
    base = os.environ.get("LOCALAPPDATA", "").strip()
    if not base:
        raise ConfigError(
            "LOCALAPPDATA is not set, so no safe writable data directory can be "
            "determined. Refusing to fall back to a temporary directory, which "
            "would risk losing the journal. Set LOCALAPPDATA to a writable "
            "folder (for example C:\\Users\\<you>\\AppData\\Local), or set "
            "TRADEQUEST2_DB to an explicit database path, and start again."
        )
    candidate = Path(base)
    if not candidate.is_absolute():
        raise ConfigError(
            f"LOCALAPPDATA is not an absolute path: {base!r}. Refusing to "
            "continue because the data directory would be ambiguous."
        )
    return candidate / APP_DIR_NAME


def _resolve_data_dir() -> Path:
    """Writable data root: project ``data/`` in dev, %LOCALAPPDATA% when frozen.

    Development behaviour is unchanged: ``<project>/data``.  When frozen the
    directory is deliberately taken *outside* the bundle so the journal is not
    written into a temporary extraction directory.
    """
    if is_frozen():
        return user_data_dir()
    return PROJECT_ROOT / "data"


DATA_DIR = _resolve_data_dir()
# The existing architecture created this directory at import time; keep that
# behaviour so development and startup paths are unchanged.  In frozen mode this
# is the per-user directory, which is safe to create.
DATA_DIR.mkdir(parents=True, exist_ok=True)

HOST = "127.0.0.1"  # mandatory - never bind to 0.0.0.0
DEFAULT_PORT = 8001

# --- database ------------------------------------------------------------
_db_env = os.environ.get("TRADEQUEST2_DB", "").strip()
DB_PATH = Path(_db_env).resolve() if _db_env else (DATA_DIR / "tradequest_v2.db")
DB_URL = os.environ.get("TRADEQUEST2_DB_URL") or f"sqlite:///{DB_PATH}"

# backups live next to the active database (keeps test backups isolated
# from the real application backups when TRADEQUEST2_DB is overridden)
BACKUP_DIR = DB_PATH.parent / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "TRADEQUEST2_CORS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"  # frontend_v2 dev server
        "http://localhost:4173,http://127.0.0.1:8001,http://localhost:8001",
    ).split(",")
    if origin.strip()
]

# --- gamification constants (approved values - see PHASE1_BLUEPRINT.md) --
XP_TRADE_CREATE = 20
XP_QUICK_REVIEW = 15
XP_DEEP_REVIEW = 30
XP_LESSON = 10
XP_LESSON_CAP_PER_REVIEW = 3
XP_EMOTIONAL_FIRST_OF_DAY = 10
XP_EMOTIONAL_ADDITIONAL = 2
XP_DAILY_REVIEW = 15
XP_WEEKLY_REVIEW = 30

# Consistency quest rewards are UNDECIDED.  They are configured through the
# quest catalog (see services/quests.py) as ``None`` which means "not yet
# claimable"; defining a value later requires no schema or ledger change.
QUEST_TIERS = {"bronze": 25, "silver": 50, "gold": 100}

MAX_BACKUPS = 10

# --- streak break & recovery (approved specification) -------------------------
# A "qualifying active day" is a LOCAL calendar day on which the user completed
# at least one journaling/learning activity.  Trade capture/close, trade edits,
# P&L changes and duplicate submissions never qualify: this feature must never
# incentivise trading.  A day counts at most once however many activities occur.
STREAK_QUALIFYING_ACTIVITIES = (
    "daily_review", "weekly_review", "quick_review",
    "deep_review", "lesson", "emotional_entry",
)

# A break is only eligible when the previous run reached this many days.
STREAK_MIN_DAYS = 3
# Distinct qualifying active days required to finish the Recovery Quest.
STREAK_RECOVERY_TARGET_DAYS = 2

# Approved quest rewards (existing tiers - no new XP amounts invented).
XP_STREAK_REFLECTION = 25   # RC-01, bronze tier (same as RF-04 / FT-01)
XP_STREAK_RECOVERY = 50     # RC-02, silver tier (same as RF-01..03)

# RC-01 / RC-02 are per-event quests: each independent streak break may claim
# the reward again, so amounts are looked up per quest code.
STREAK_RECOVERY_XP = {"RC-01": XP_STREAK_REFLECTION, "RC-02": XP_STREAK_RECOVERY}
PER_EVENT_QUEST_CODES = ("RC-01", "RC-02")

# UiPreference key for the user-facing on/off switch.  Tracking is ON by
# default: an absent row means enabled.
STREAK_PREF_KEY = "streak_tracking_enabled"
# AppMeta keys holding the activation baseline (spec F/G).
STREAK_META_SINCE = "streak_tracking_since"
STREAK_META_DISABLED_AT = "streak_tracking_disabled_at"


def screenshot_allowed_dirs() -> list[str]:
    """Directories the screenshot endpoint may serve files from.

    Read per request (not cached) so the environment can be changed without
    restarting the app and so tests can inject their own temporary roots.
    An empty list means "nothing is permitted" - the endpoint fails closed.
    """
    raw = os.environ.get("TRADEQUEST2_SCREENSHOT_DIRS", "")
    return [p.strip() for p in raw.split(os.pathsep) if p.strip()]


def static_dir() -> Path:
    """Directory holding the built frontend SPA (Phase 3).

    Additive, guarded integration: when the directory exists and contains an
    index.html, main.py serves it locally (single-port launch).  Otherwise the
    app keeps serving the JSON API only - no behavior change for dev mode.

    Development: ``<project>/frontend_v2/dist``.
    Frozen:      ``<sys._MEIPASS>/frontend_v2/dist`` - read-only bundled assets,
                 resolved from the bundle rather than the working directory.
    ``TRADEQUEST2_STATIC_DIR`` still overrides both.
    """
    env = os.environ.get("TRADEQUEST2_STATIC_DIR", "").strip()
    if env:
        return Path(env).resolve()
    bundle = bundle_dir()
    if bundle is not None:
        return bundle / "frontend_v2" / "dist"
    return PROJECT_ROOT / "frontend_v2" / "dist"


def now_local() -> dt.datetime:
    """Current local wall-clock time with timezone attached.

    All XP day/week grouping uses *local* calendar dates consistently - the
    server never mixes UTC dates and local dates.
    """
    return dt.datetime.now().astimezone()


def today_local() -> dt.date:
    return now_local().date()


def iso_week_local(day: dt.date | dt.datetime | None = None) -> tuple[int, int]:
    """(iso_year, iso_week) for a local date (defaults to today)."""
    d = day if day is not None else today_local()
    if isinstance(d, dt.datetime):
        d = d.astimezone().date()
    iso = d.isocalendar()
    return iso[0], iso[1]
