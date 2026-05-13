@echo off
setlocal EnableExtensions
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [xyz-scrcpy] Missing .venv\Scripts\python.exe. Create a venv under this repo ^(e.g. run install_xyz.py or `uv venv` + install deps^) then retry.
    popd
    exit /b 1
)
set "PATH=%~dp0vendor;%PATH%"
".venv\Scripts\python.exe" "%~dp0bin\launch_with_checks.py" %*
set "ERR=%ERRORLEVEL%"
popd
exit /b %ERR%
