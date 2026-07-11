@echo off
if exist "%~dp0pkg_launchers\windows\installer.bat" (
  call "%~dp0pkg_launchers\windows\installer.bat" %*
) else (
  call "%~dp0launchers\windows\installer.bat" %*
)