@echo off
pushd "%~dp0"
setlocal enabledelayedexpansion

echo [1/4] Checking for uv...
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo uv is not installed. Install from https://github.com/astral-sh/uv
    pause
    exit /b 1
)

echo [2/4] Creating virtual environment...
if not exist .venv (
    uv venv .venv
)

echo [3/4] Installing dependencies (see pyproject.toml / .requirements.txt)...
uv pip install -r .requirements.txt

echo [4/4] Setting up vendor binaries (scrcpy)...
.venv\Scripts\python.exe setup_vendor.py

echo.
echo Local environment ready. To install user copy + Task Scheduler, run:
echo   .venv\Scripts\python.exe install_xyz.py
echo Or non-interactive: .venv\Scripts\python.exe install_xyz.py --action install --yes
echo Desktop launcher: use start.bat or the shortcut created by install_xyz.py
popd
pause
