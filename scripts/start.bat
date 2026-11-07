@echo off
rem Qing-Ledger start script (member 1). Locates project root from any cwd.
setlocal
cd /d "%~dp0.."

rem 1. Virtualenv: delivery uses the project-local .venv, not global Python.
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtualenv .venv not found. Run scripts\setup.bat first.
    exit /b 1
)

rem 2. Dependency check; do not silently upgrade here.
".venv\Scripts\python.exe" -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Flask missing in .venv. Re-run scripts\setup.bat.
    exit /b 1
)

rem 3. Build artifact: delivery mode serves web/ static files together with /api.
if not exist "web\index.html" (
    echo [ERROR] web\index.html not found. Build the frontend and copy dist to web first.
    exit /b 1
)

rem 4. Start: listen on 127.0.0.1:5000, debug and reloader off, single process.
echo [INFO] Starting Qing-Ledger at http://127.0.0.1:5000
".venv\Scripts\python.exe" backend\run.py
if errorlevel 1 (
    echo [ERROR] App failed to start. See output above.
    exit /b 1
)

endlocal
