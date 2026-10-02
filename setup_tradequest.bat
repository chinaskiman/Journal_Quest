@echo off
setlocal
rem ============================================================
rem  Trade Quest - one-time setup: create venv + install deps
rem  (does NOT touch any existing database or data)
rem ============================================================
set "ROOT=%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH. Install Python 3.11+ first.
    pause
    exit /b 1
)

rem --- Python version check -------------------------------------------------
rem Trade Quest V2 requires Python 3.11 or newer.  This check only *reports*:
rem it never installs, upgrades, or modifies anything.  If the version is
rem supported, execution continues exactly as before.
set "PYVER=unknown"
for /f "tokens=*" %%v in ('python -c "import platform;print(platform.python_version())" 2^>nul') do set "PYVER=%%v"
python -c "import sys;raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Unsupported Python version: %PYVER%
    echo         Trade Quest V2 requires Python 3.11 or newer.
    echo         This script does not install or upgrade Python for you.
    echo         Install Python 3.11+ from https://www.python.org/downloads/
    echo         ^(remember to tick "Add python.exe to PATH"^), then re-run
    echo         setup_tradequest.bat.
    pause
    exit /b 1
)
echo Using Python %PYVER% ^(3.11+ required^).

cd /d "%ROOT%backend"
if not exist .venv (
    echo Creating virtual environment ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

echo Installing backend dependencies ...
.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed - see output above.
    pause
    exit /b 1
)

echo.
rem --- Phase 3 frontend dependencies (optional; backend setup is unaffected) ---
where npm >nul 2>nul
if errorlevel 1 (
    echo [NOTE] npm was not found - skipping frontend_v2 dependencies.
    echo        To build/run the Phase 3 UI install Node.js 20+ and run:
    echo          cd frontend_v2 ^&^& npm install ^&^& npm run build
) else (
    echo Installing frontend_v2 dependencies ...
    pushd "%ROOT%frontend_v2"
    call npm install
    if errorlevel 1 (
        echo [NOTE] npm install failed - the backend still works; retry later
        echo        from frontend_v2 with: npm install
    ) else (
        echo Building the Phase 3 frontend so the backend can serve it ...
        call npm run build
        if errorlevel 1 echo [NOTE] Frontend build failed - run it later from frontend_v2.
    )
    popd
)

echo.
echo [OK] Setup complete. Use start_tradequest_v2.bat to launch the app.
pause
endlocal
