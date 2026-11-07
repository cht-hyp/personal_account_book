@echo off
rem Qing-Ledger release packager (member 1). Builds the frontend and zips the delivery package.
rem Usage: scripts\package.bat [version]   (default version v1.0.0)
setlocal
cd /d "%~dp0.."

set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=v1.0.0"
set "STAGE=release\qing-ledger-%VERSION%-windows"

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm not found. Install Node.js and add it to PATH.
    exit /b 1
)

echo [INFO] Installing frontend deps (npm ci) ...
call npm --prefix frontend ci
if errorlevel 1 (
    echo [ERROR] npm ci failed.
    exit /b 1
)

echo [INFO] Building frontend (npm run build) ...
call npm --prefix frontend run build
if errorlevel 1 (
    echo [ERROR] npm run build failed.
    exit /b 1
)

rem Rebuild web/ from the fresh dist so Flask serves the latest assets.
echo [INFO] Copying frontend/dist to web/ ...
if exist "web" rmdir /s /q "web"
mkdir "web"
xcopy /e /i /y "frontend\dist\*" "web\" >nul
if errorlevel 1 (
    echo [ERROR] Copying dist to web failed.
    exit /b 1
)

rem Assemble the delivery directory (README 16.2): backend + web + examples + scripts + requirements + README.
echo [INFO] Assembling %STAGE% ...
if exist "release" rmdir /s /q "release"
mkdir "%STAGE%"
xcopy /e /i /y "backend" "%STAGE%\backend\" >nul
xcopy /e /i /y "web" "%STAGE%\web\" >nul
xcopy /e /i /y "examples" "%STAGE%\examples\" >nul
xcopy /e /i /y "scripts" "%STAGE%\scripts\" >nul
copy /y "requirements.txt" "%STAGE%\" >nul
copy /y "README.md" "%STAGE%\" >nul

rem Strip interpreter caches that must not ship.
for /d /r "%STAGE%" %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
del /s /q "%STAGE%\*.pyc" >nul 2>nul

echo [INFO] Zipping to release\%VERSION%.zip ...
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%' -DestinationPath 'release\%VERSION%.zip' -Force"
if errorlevel 1 (
    echo [ERROR] Zip failed.
    exit /b 1
)

echo [OK] Release package ready: release\%VERSION%.zip
echo      Verify by unzipping to a clean directory, then run scripts\setup.bat and scripts\start.bat.
endlocal
