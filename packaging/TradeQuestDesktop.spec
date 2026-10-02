# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec - Trade Quest V2 DESKTOP shell (Phase C spike).

Build mode : --onedir (never --onefile - PyInstaller #8817 breaks uvicorn Ctrl+C)

Run from the project root with the disposable build venv:

    .buildvenv\\Scripts\\python -m PyInstaller --noconfirm --clean ^
        --distpath dist-desktop --workpath build-desktop ^
        packaging\\TradeQuestDesktop.spec

Desktop shell extras beyond the Phase B backend build
-----------------------------------------------------
pywebview needs three groups of NATIVE payloads, which PyInstaller's static
analysis will not discover:

  * ``pythonnet/runtime/Python.Runtime.dll``   (.NET interop)
  * ``clr_loader/ffi/dlls/*/ClrLoader.dll``    (host runtime loader)
  * ``webview/lib/runtimes/win-*/native/WebView2Loader.dll``  (Edge WebView2)

They are collected as *binaries* so the frozen app can create its window.  The
WebView2 **runtime** itself is NOT bundled - pywebview uses the Evergreen
runtime installed on the machine (see docs/SETUP_AND_OPERATIONS.md).

Everything else (app2, SPA, loopback-only security, exclusions) matches
``TradeQuest.spec``.
"""
import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

PROJECT_ROOT = os.path.abspath(os.getcwd())
BACKEND = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend_v2", "dist")

# --- bundled SPA (read-only assets) ----------------------------------------
datas = [(FRONTEND_DIST, os.path.join("frontend_v2", "dist"))]

# --- native payloads for the desktop shell ---------------------------------
binaries = []
for module in ("pythonnet", "clr_loader", "webview"):
    binaries += collect_dynamic_libs(module)
datas += collect_data_files("webview")

hiddenimports = [
    # --- desktop shell -----------------------------------------------------
    "webview",
    "webview.platforms",
    "webview.platforms.edgechromium",   # WebView2 backend (Windows default)
    "clr",                             # .NET interop used by edgechromium
    "pythonnet",
    "clr_loader",
    # --- backend (same list as the Phase B spec) --------------------------
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "pydantic.deprecated.decorator",
    "email_validator",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
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
hiddenimports += collect_submodules("app2.services")
hiddenimports += collect_submodules("app2.routers")

excludes = [
    "app",                        # V1 backend must never ship in the V2 bundle
    "pytest", "_pytest", "pytest_asyncio",
    "unittest", "pydoc", "doctest",
    "PyInstaller", "pyinstaller_hooks_contrib", "setuptools", "pip", "altgraph",
    "tkinter", "IPython",
    # other desktop backends we do not use
    "PyQt5", "PyQt6", "PySide2", "PySide6", "gtk", "cefpython3",
]

block_cipher = None

a = Analysis(
    [os.path.join(BACKEND, "run_desktop.py")],
    pathex=[BACKEND],
    binaries=binaries,
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
    upx=False,
    console=True,          # diagnostics visible; no GUI shell in this phase
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
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