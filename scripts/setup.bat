@echo off
rem Qing-Ledger environment setup (member 1). Locates project root from any cwd.
rem Usage:
rem   scripts\setup.bat        install runtime deps (requirements.txt)
rem   scripts\setup.bat dev    install test deps (requirements-dev.txt)
setlocal
cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3 and add it to PATH.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtualenv .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtualenv.
        exit /b 1
    )
)

rem Purge a possibly-corrupted pip cache to avoid deserialization warnings.
".venv\Scripts\python.exe" -m pip cache purge >nul 2>nul

set "REQ=requirements.txt"
if /i "%~1"=="dev" set "REQ=requirements-dev.txt"

rem Direct PyPI can be blocked for some packages; try mirrors first, then official.
set "OK="
for %%M in (
    https://pypi.tuna.tsinghua.edu.cn/simple
    https://mirrors.aliyun.com/pypi/simple/
    https://pypi.mirrors.ustc.edu.cn/simple/
    https://pypi.org/simple
) do (
    if not defined OK (
        echo [INFO] Trying mirror %%M for %REQ% ...
        ".venv\Scripts\python.exe" -m pip install -i %%M -r %REQ%
        if not errorlevel 1 set "OK=1"
    )
)

if not defined OK (
    echo [ERROR] Dependency install failed. Check network, or run manually:
    echo         .venv\Scripts\python.exe -m pip install -i MIRROR_URL -r %REQ%
    exit /b 1
)

echo [OK] Environment ready.
echo       Start app: scripts\start.bat
echo       Run tests: scripts\setup.bat dev then .venv\Scripts\python.exe -m pytest tests\backend -v
endlocal
