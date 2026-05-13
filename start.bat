@echo off
pushd "%~dp0"
setlocal

if not exist .venv (
    echo Virtual environment not found. Please run installer.bat first.
    popd
    pause
    exit /b 1
)

:: Add vendor directory to PATH so adb.exe can be found
set PATH=%~dp0vendor;%PATH%

echo Starting xyz-scrcpy...
.venv\Scripts\python.exe bin\menu.py
popd
pause
