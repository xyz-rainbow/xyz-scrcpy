@echo off
setlocal EnableExtensions
pushd "%~dp0..\.."
call "%~dp0xyz-scrcpy.cmd" %*
set "ERR=%ERRORLEVEL%"
popd
exit /b %ERR%