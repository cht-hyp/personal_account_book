@echo off
setlocal
cd /d "%~dp0.."
set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=v1.0.0"
python scripts\package.py --version "%VERSION%"
exit /b %errorlevel%
