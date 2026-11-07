@echo off
rem 轻账本 启动脚本（1 号）。从任意目录运行都会定位到项目根目录。
setlocal
cd /d "%~dp0.."

rem 1. 虚拟环境：交付版依赖项目内 .venv，不修改全局 Python。
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 未找到虚拟环境 .venv，请先运行 scripts\setup.bat。
    exit /b 1
)

rem 2. 依赖：确认 Flask 已安装；此处不静默升级，缺依赖给出可操作提示。
".venv\Scripts\python.exe" -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 虚拟环境缺少 Flask，请重新运行 scripts\setup.bat 安装依赖。
    exit /b 1
)

rem 3. 构建产物：交付版由 Flask 同时提供 web/ 静态页面和 /api 接口。
if not exist "web\index.html" (
    echo [ERROR] 未找到 web\index.html，前端构建产物缺失。
    echo        请先构建前端并把 dist 复制为 web，或联系 7 号确认构建产物。
    exit /b 1
)

rem 4. 启动：交付版监听 127.0.0.1:5000，关闭 debug 与自动重载、单进程。
echo [INFO] 正在启动轻账本，浏览器访问 http://127.0.0.1:5000
".venv\Scripts\python.exe" backend\run.py
if errorlevel 1 (
    echo [ERROR] 应用启动失败，请查看上方输出。
    exit /b 1
)

endlocal
