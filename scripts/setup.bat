@echo off
setlocal
cd /d "%~dp0.."
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Install Python 3 and add it to PATH first.
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Could not create the project virtual environment.
    exit /b 1
)
set "REQ=requirements.txt"
if /i "%~1"=="dev" set "REQ=requirements-dev.txt"
if not exist "%REQ%" (
    echo [ERROR] Dependency file not included. Use the source repository for development.
    exit /b 1
)
set "OK="
for %%M in (
    https://pypi.org/simple
    https://pypi.tuna.tsinghua.edu.cn/simple
    https://mirrors.aliyun.com/pypi/simple/
    https://pypi.mirrors.ustc.edu.cn/simple/
) do (
    if not defined OK (
        echo [INFO] Installing runtime dependencies from %%M ...
        ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-input -i %%M -r "%REQ%"
        if errorlevel 0 if not errorlevel 1 (
            ".venv\Scripts\python.exe" -c "import flask" >nul 2>nul
            if errorlevel 0 if not errorlevel 1 set "OK=1"
        )
    )
)
if not defined OK (
    echo [ERROR] Dependencies are not ready. Check the network and try again.
    exit /b 1
)
echo [OK] Runtime is ready. Run scripts\start.bat to launch.
endlocal
exit /b 0
