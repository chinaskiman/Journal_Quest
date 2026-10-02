@echo off
setlocal
rem ============================================================
rem  Trade Quest - run the full test suite
rem  (v1 app tests + v2 app tests; both use isolated temp databases)
rem ============================================================
set "ROOT=%~dp0"
set "VENV=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%VENV%" (
    echo [ERROR] Virtual environment not found. Run setup_tradequest.bat first.
    pause
    exit /b 1
)

cd /d "%ROOT%backend"
"%VENV%" -m pytest -q
if errorlevel 1 (
    echo.
    echo [FAILED] Tests did not pass - see output above.
    pause
    exit /b 1
)

rem --- Phase 3 frontend (optional: only when its dependencies are installed) ---
if exist "%ROOT%frontend_v2\node_modules" (
    echo.
    echo Running Phase 3 frontend tests ^(frontend_v2^) ...
    pushd "%ROOT%frontend_v2"
    call npm test
    if errorlevel 1 (
        popd
        echo.
        echo [FAILED] Frontend tests did not pass - see output above.
        pause
        exit /b 1
    )
    popd
) else (
    echo.
    echo [SKIP] frontend_v2\node_modules not found - frontend tests skipped.
    echo        Install them with: cd frontend_v2 ^&^& npm install
)

echo.
echo [OK] All tests passed.
pause
endlocal
