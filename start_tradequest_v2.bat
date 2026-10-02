@echo off
setlocal
rem ============================================================
rem  Trade Quest v2 - local application start (backend on 127.0.0.1)
rem  Serves the v2 API on port 8001 and the built frontend if present.
rem ============================================================
set "ROOT=%~dp0"
set "VENV=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%VENV%" (
    echo [ERROR] Python virtual environment not found at:
    echo   %VENV%
    echo Run setup_tradequest.bat first to install dependencies.
    pause
    exit /b 1
)

rem --- Interpreter version check (read-only) --------------------------------
rem The venv interpreter must be Python 3.11+.  This never installs or
rem upgrades anything; on a supported version the launcher continues unchanged.
"%VENV%" -c "import sys;raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The virtual environment uses an unsupported Python version.
    echo         Trade Quest V2 requires Python 3.11 or newer.
    echo         This script does not install or upgrade Python for you.
    echo         Re-run setup_tradequest.bat with Python 3.11+ on PATH.
    pause
    exit /b 1
)

echo Starting Trade Quest v2 backend on http://127.0.0.1:8001 ...
echo Press Ctrl+C to stop.
rem Screenshot allow-list: directories the /screenshot endpoint may serve
rem from.  Preset to the user's Pictures folder; override by defining
rem TRADEQUEST2_SCREENSHOT_DIRS before launching ( ';' separates entries).
if not defined TRADEQUEST2_SCREENSHOT_DIRS set "TRADEQUEST2_SCREENSHOT_DIRS=%USERPROFILE%\Pictures"
cd /d "%ROOT%backend"
"%VENV%" -m uvicorn app2.main:app --host 127.0.0.1 --port 8001
if errorlevel 1 (
    echo.
    echo [ERROR] The backend failed to start. Check the messages above.
    pause
    exit /b 1
)
endlocal
