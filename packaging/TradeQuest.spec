# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec - Trade Quest V2 (Phase B experimental build spike).

Build mode : --onedir  (NEVER --onefile - see docs/SETUP_AND_OPERATIONS.md:
             PyInstaller issue #8817 - onefile breaks uvicorn Ctrl+C shutdown)

Run from the project root with the disposable build venv:

    .buildvenv\\Scripts\\python -m PyInstaller --noconfirm --clean ^
        --distpath dist --workpath build packaging\\TradeQuest.spec

What goes in
------------
* ``app2`` (V2 backend) and its runtime dependencies.
* ``frontend_v2/dist`` as BUNDLED, READ-ONLY data.  The backend serves it from
  ``sys._MEIPASS`` via ``config.static_dir()`` (Phase A frozen resolution).

What stays out
--------------
* the V1 backend (``app``), the V1 database, the v2 database, ``data/``,
  ``tests_v2``/``tests``, ``node_modules``, screenshots and logs.  The bundle must
  never contain user data - writable state lives in ``%LOCALAPPDATA%\\TradeQuest``.
"""
import os

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = os.path.abspath(os.getcwd())
BACKEND = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend_v2", "dist")

# --- the bundled SPA (read-only assets) -------------------------------------
datas = [
    (FRONTEND_DIST, os.path.join("frontend_v2", "dist")),
]

# Third-party runtime imports PyInstaller's static analysis can miss.
hiddenimports = [
    # SQLAlchemy dialects / plugins
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    # Pydantic v2 runtime
    "pydantic.deprecated.decorator",
    "email_validator",
    # uvicorn loop/protocol implementations
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    # app packages (explicit, so the bundle never depends on sys.path order)
    "app2",
    "app2.config",
    "app2.db",
    "app2.main",
    "app2.models",
    "app2.schemas",
    "app2.routers.trades",
    "app2.routers.reviews",
    "app2.routers.emotional",
    "app2.routers.checkins",
    "app2.routers.settings",
    "app2.routers.gamification",
    "app2.routers.dashboard",
    "app2.services.quests",
    "app2.services.achievements",
    "app2.services.levels",
    "app2.services.streaks",
    "app2.services.xp",
    "app2.services.activity",
    "app2.services.dashboard",
]
# collect any app2.service / app2.routers modules added later without editing here
hiddenimports += collect_submodules("app2.services")
hiddenimports += collect_submodules("app2.routers")

# Exclusions: development/test tooling and the entire V1 application.
excludes = [
    # V1 backend must never ship in the V2 bundle
    "app",
    # dev / test only - not needed at runtime
    "pytest",
    "_pytest",
    "pytest_asyncio",
    "unittest",
    "pydoc",
    "doctest",
    # packaging/build tooling
    "PyInstaller",
    "pyinstaller_hooks_contrib",
    "setuptools",
    "pip",
    "altgraph",
    "tkinter",
    "IPython",
]

block_cipher = None

a = Analysis(
    [os.path.join(BACKEND, "run_frozen.py")],
    pathex=[BACKEND],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TradeQuest",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX packing is a well-known antivirus false-positive source
    console=True,       # diagnostics must be visible in this build spike
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,   # build for the host interpreter (Windows x64 here)
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TradeQuest",
)