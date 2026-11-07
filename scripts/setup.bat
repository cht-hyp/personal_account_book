@echo off
rem 轻账本 环境准备脚本（1 号）。从任意目录运行都会定位到项目根目录。
rem 用法：
rem   scripts\setup.bat        安装运行依赖 requirements.txt
rem   scripts\setup.bat dev    安装测试依赖 requirements-dev.txt（含运行依赖）
setlocal
cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到 python，请先安装 Python 3 并加入 PATH。
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] 正在创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] 创建虚拟环境失败。
        exit /b 1
    )
)

rem 清理可能损坏的 pip 缓存，避免 "Cache entry deserialization failed" 干扰解析。
".venv\Scripts\python.exe" -m pip cache purge >nul 2>nul

set "REQ=requirements.txt"
if /i "%~1"=="dev" set "REQ=requirements-dev.txt"

rem 国内直连 PyPI 常见部分包（如 jinja2）被拦、返回空版本列表；
rem 依次尝试国内镜像，最后回退官方源，任一成功即停止。
set "OK="
for %%M in (
    https://pypi.tuna.tsinghua.edu.cn/simple
    https://mirrors.aliyun.com/pypi/simple/
    https://pypi.mirrors.ustc.edu.cn/simple/
    https://pypi.org/simple
) do (
    if not defined OK (
        echo [INFO] 尝试镜像 %%M 安装 %REQ% ...
        ".venv\Scripts\python.exe" -m pip install -i %%M -r %REQ%
        if not errorlevel 1 set "OK=1"
    )
)

if not defined OK (
    echo [ERROR] 依赖安装失败，请检查网络后重试；也可手动指定镜像：
    echo         .venv\Scripts\python.exe -m pip install -i 镜像地址 -r %REQ%
    exit /b 1
)

echo [OK] 环境准备完成。
echo      启动应用：scripts\start.bat
echo      运行测试：scripts\setup.bat dev 后执行 .venv\Scripts\python.exe -m pytest tests\backend -v
endlocal
