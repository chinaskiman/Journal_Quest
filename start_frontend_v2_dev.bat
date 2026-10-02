@echo off
setlocal
rem ============================================================
rem  Trade Quest v2 - development frontend (Vite dev server)
rem  Serves the Phase-3 UI on http://127.0.0.1:5174 and proxies
rem  /api requests to the local backend on 127.0.0.1:8001.
rem  Run start_backend_v2_dev.bat in another window first.
rem ============================================================
set "ROOT=%~dp0"
set "WEB=%ROOT%frontend_v2"

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found on PATH. Install Node.js 20+ first.
    pause
    exit /b 1
)

if not exist "%WEB%\node_modules" (
    echo Installing frontend dependencies ^(first run only^) ...
    pushd "%WEB%"
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed - see output above.
        popd
        pause
        exit /b 1
    )
    popd
)

echo Trade Quest v2 frontend: http://127.0.0.1:5174
echo (API proxied to http://127.0.0.1:8001 - start the backend first)
echo Press Ctrl+C to stop.
pushd "%WEB%"
call npm run dev
if errorlevel 1 (
    echo.
    echo [ERROR] The dev server failed to start. Check the messages above.
    popd
    pause
    exit /b 1
)
popd
endlocal
