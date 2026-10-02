"""Frozen (PyInstaller) entry point for Trade Quest V2 - Phase B build spike.

Why this file exists
--------------------
``app2/main.py`` launches uvicorn with the *string* app-spec
``"app2.main:app"``.  That form works in development because the ``backend``
folder is on ``sys.path``, but it cannot work in a frozen bundle: uvicorn
resolves the string through ``importlib.import_module("app2.main")``, and a
frozen app is not importable by that name from ``sys.path``.  Verified failure
mode (frozen-like, backend not on sys.path):

    import_from_string("app2.main:app") -> ModuleNotFoundError: No module named 'app2'

Passing the already-imported *object* needs no name lookup, so this entry point
imports the app first and hands the object to uvicorn.  ``main.py`` is left
untouched, so the ``.bat`` development workflow is unaffected.

Import order matters and is deliberate: ``app2.config`` resolves paths at import
time, and ``app2.db`` builds its engine from ``config.DB_URL`` at import time.
Importing ``app2.main`` therefore pulls config in first, which is exactly what the
frozen path resolution (Phase A) relies on.

Security
--------
Binds to ``127.0.0.1`` only - the value comes from ``config.HOST``, which is
hard-coded and has no environment override.
"""
from __future__ import annotations

import sys


def _fail(message: str, detail: str | None = None) -> None:
    """Print a startup failure clearly instead of dying silently."""
    print("")
    print("=" * 70)
    print("[Trade Quest] STARTUP FAILED")
    print("=" * 70)
    print(message)
    if detail:
        print("")
        print(detail)
    print("")
    print("If this persists, run the application in development mode")
    print("(start_tradequest_v2.bat) to see the full traceback.")
    print("=" * 70)
    sys.stderr.flush()
    sys.stdout.flush()


def main() -> int:
    try:
        # 1. config first (path resolution + host), then db/engine, then app.
        from app2 import config
        from app2.main import app
    except Exception:  # noqa: BLE001 - surface anything to the console
        import traceback

        _fail(
            "The Trade Quest backend could not be loaded from the bundle.",
            traceback.format_exc(),
        )
        return 1

    try:
        # Read-only assets from the bundle; writable data from %LOCALAPPDATA%.
        print(f"[Trade Quest] mode      : frozen")
        print(f"[Trade Quest] host      : {config.HOST}")
        print(f"[Trade Quest] data dir  : {config.DATA_DIR}")
        print(f"[Trade Quest] static dir: {config.static_dir()}")
        sys.stdout.flush()
    except Exception:  # noqa: BLE001 - diagnostics must never block startup
        _fail("Could not resolve application paths.")
        return 1

    try:
        import uvicorn
    except Exception:  # noqa: BLE001
        import traceback

        _fail("uvicorn is missing from the bundle.", traceback.format_exc())
        return 1

    try:
        # App OBJECT, not the "module:attr" string - see module docstring.
        uvicorn.run(app, host=config.HOST, port=config.DEFAULT_PORT)
    except KeyboardInterrupt:
        print("\n[Trade Quest] shutting down.")
    except Exception:  # noqa: BLE001
        import traceback

        _fail("The Trade Quest backend stopped unexpectedly.",
              traceback.format_exc())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())