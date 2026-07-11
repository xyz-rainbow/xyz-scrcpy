@echo off
setlocal EnableExtensions
pushd "%~dp0..\.."
set "PATH=%~dp0..\..\vendor;%PATH%"
uv run --link-mode=copy bin\launch_with_checks.py %*
set "ERR=%ERRORLEVEL%"
popd
exit /b %ERR%
