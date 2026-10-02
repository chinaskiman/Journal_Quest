@echo off
setlocal
rem ============================================================
rem  Trade Quest v2 - development backend with auto-reload
rem  (local only: 127.0.0.1:8001)
rem ============================================================
set "ROOT=%~dp0"
set "VENV=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%VENV%" (
    echo [ERROR] Virtual environment not found. Run setup_tradequest.bat first.
    pause
    exit /b 1
)

echo Dev backend: http://127.0.0.1:8001  (docs: /docs)
rem Screenshot allow-list (see start_tradequest_v2.bat) - override freely.
if not defined TRADEQUEST2_SCREENSHOT_DIRS set "TRADEQUEST2_SCREENSHOT_DIRS=%USERPROFILE%\Pictures"
cd /d "%ROOT%backend"
"%VENV%" -m uvicorn app2.main:app --host 127.0.0.1 --port 8001 --reload
if errorlevel 1 (
    echo [ERROR] Dev backend failed to start.
    pause
    exit /b 1
)
endlocal
