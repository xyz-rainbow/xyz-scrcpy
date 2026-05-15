@echo off
REM XYZ-scrcpy Windows dev installer - interactive CMD menu (not full-screen TUI).
REM VT/colors: enabled automatically when possible; ESC from PowerShell (works under PS hosts).
REM Confirmations: [Y/n] - Enter or empty = Yes.

setlocal EnableExtensions EnableDelayedExpansion
pushd "%~dp0" || exit /b 1

call :ensure_uv
set "UVRET=!errorlevel!"
if "!UVRET!"=="2" (
  echo.
  echo You declined to install uv. Install manually from https://github.com/astral-sh/uv
  pause
  goto :cleanup_exit0
)
if "!UVRET!"=="1" (
  echo.
  echo uv is still not available after the install attempt.
  pause
  goto :cleanup_exit1
)

if exist ".venv\Scripts\python.exe" goto :after_venv_exists

call :confirm_yes_no "Create .venv and install dependencies (may take a few minutes)"
if "!CONFIRM_RESULT!"=="0" (
  echo Skipping environment setup. Use menu option [1] later to create or refresh .venv.
  goto :pre_menu_once
)

call :do_bootstrap
if errorlevel 1 (
  echo Bootstrap failed.
  pause
  goto :cleanup_exit1
)

:after_venv_exists
:pre_menu_once
if defined PRE_MENU_DONE goto :main_loop
set "PRE_MENU_DONE=1"

call :try_enable_vt
call :init_esc

:main_loop
call :get_term_width
call :draw_menu_frame
echo.
echo   [1] Update / create dev environment  (.venv, deps, vendor)
echo   [2] Install (system PATH shim / service - interactive Python prompts)
echo   [3] Uninstall (interactive Python prompts)
echo   [4] Diagnose (Windows PATH / shim / adb - install_xyz.py)
echo   [5] Sync launcher alias only (install_xyz.py)
echo   [Q] Quit
echo.
REM choice /C 12345Q : ERRORLEVEL 1..5 for 1..5, 6 for Q
choice /C 12345Q /N /M "Select [1-5 or Q]: "
set "MC=!errorlevel!"

if "!MC!"=="6" goto :cleanup_exit0
if "!MC!"=="1" goto :opt_refresh
if "!MC!"=="2" goto :opt_install
if "!MC!"=="3" goto :opt_uninstall
if "!MC!"=="4" goto :opt_diagnose
if "!MC!"=="5" goto :opt_syncalias
goto :main_loop

:opt_refresh
call :confirm_yes_no "Update or create .venv, run uv pip install, and setup_vendor (uses network)"
if "!CONFIRM_RESULT!"=="0" goto :main_loop
if not exist ".venv\Scripts\python.exe" (
  call :confirm_yes_no "Create new .venv in this repo now"
  if "!CONFIRM_RESULT!"=="0" goto :main_loop
)
call :do_bootstrap
if errorlevel 1 (
  echo Update failed.
  pause
)
goto :main_loop

:opt_install
if not exist ".venv\Scripts\python.exe" (
  echo No .venv Python found. Choose [1] first to create the dev environment.
  pause
  goto :main_loop
)
call :confirm_yes_no "Run INSTALL via install_xyz.py (you will be asked again inside Python)"
if "!CONFIRM_RESULT!"=="0" goto :main_loop
call :run_install_xyz --action install
goto :main_loop

:opt_uninstall
if not exist ".venv\Scripts\python.exe" (
  echo No .venv Python found. Choose [1] first to create the dev environment.
  pause
  goto :main_loop
)
call :confirm_yes_no "Run UNINSTALL via install_xyz.py (you will be asked again inside Python)"
if "!CONFIRM_RESULT!"=="0" goto :main_loop
call :run_install_xyz --action uninstall
goto :main_loop

:opt_diagnose
if not exist ".venv\Scripts\python.exe" (
  echo No .venv Python found. Choose [1] first to create the dev environment.
  pause
  goto :main_loop
)
call :confirm_yes_no "Run DIAGNOSE via install_xyz.py (Windows PATH / shim / adb)"
if "!CONFIRM_RESULT!"=="0" goto :main_loop
call :run_install_xyz --action diagnose
goto :main_loop

:opt_syncalias
if not exist ".venv\Scripts\python.exe" (
  echo No .venv Python found. Choose [1] first to create the dev environment.
  pause
  goto :main_loop
)
call :confirm_yes_no "Run SYNC-ALIAS via install_xyz.py (you will be asked again inside Python)"
if "!CONFIRM_RESULT!"=="0" goto :main_loop
call :run_install_xyz --action sync-alias
goto :main_loop

REM ---------------------------------------------------------------------------
:cleanup_exit0
popd
endlocal
exit /b 0

:cleanup_exit1
popd
endlocal
exit /b 1

REM ---------------------------------------------------------------------------
REM exit /b 0 = uv already OK
REM exit /b 2 = user declined to install uv
REM exit /b 1 = install failed or uv still missing
:ensure_uv
uv --version >nul 2>&1
if not errorlevel 1 exit /b 0
echo.
echo uv was not found on PATH. It is required to manage the local .venv.
echo This will download and run the official Astral installer script (network).
call :confirm_yes_no "Install uv now via https://astral.sh/uv/install.ps1"
if "!CONFIRM_RESULT!"=="0" exit /b 2
echo.
echo Installing uv...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 (
  echo PowerShell installer returned an error.
  exit /b 1
)
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
uv --version >nul 2>&1
if errorlevel 1 (
  echo uv is still not on PATH after install. Try closing this window, open a new CMD, and run installer.bat again.
  exit /b 1
)
exit /b 0

REM ---------------------------------------------------------------------------
:do_bootstrap
if not exist ".venv" (
  echo [bootstrap] Creating virtual environment...
  uv venv .venv
  if errorlevel 1 exit /b 1
)
echo [bootstrap] Installing Python dependencies...
uv pip install -r .requirements.txt
if errorlevel 1 exit /b 1
echo [bootstrap] Running setup_vendor.py...
".venv\Scripts\python.exe" setup_vendor.py
if errorlevel 1 exit /b 1
echo [bootstrap] Done.
exit /b 0

REM ---------------------------------------------------------------------------
REM Usage: call :run_install_xyz --action install^|uninstall^|diagnose^|sync-alias
:run_install_xyz
".venv\Scripts\python.exe" install_xyz.py %1 %2
set "PYRET=!errorlevel!"
if not "!PYRET!"=="0" (
  echo.
  echo install_xyz.py exited with code !PYRET!.
  pause
  exit /b 0
)
if /i "%~1"=="--action" if /i "%~2"=="install" (
  echo.
  echo Tip: open a NEW terminal so your user PATH picks up the xyz-scrcpy shim under LocalAppData.
)
exit /b 0

REM ---------------------------------------------------------------------------
REM Enter / empty / y / yes = 1 ; n / no = 0 ; other input defaults to 1
:confirm_yes_no
echo %~1
set "XYZC="
set /p "XYZC=Confirm [Y/n]: "
if "!XYZC!"=="" set "CONFIRM_RESULT=1" & exit /b 0
if /i "!XYZC!"=="y" set "CONFIRM_RESULT=1" & exit /b 0
if /i "!XYZC!"=="yes" set "CONFIRM_RESULT=1" & exit /b 0
if /i "!XYZC!"=="n" set "CONFIRM_RESULT=0" & exit /b 0
if /i "!XYZC!"=="no" set "CONFIRM_RESULT=0" & exit /b 0
set "CONFIRM_RESULT=1"
exit /b 0

REM ---------------------------------------------------------------------------
:try_enable_vt
set "VT_OK=0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\enable_conhost_vt.ps1" >nul 2>&1
if not errorlevel 1 set "VT_OK=1"
exit /b 0

REM ---------------------------------------------------------------------------
REM ESC for CSI (reliable when run from PowerShell; cmd $E fallback)
:init_esc
set "ESC="
for /f "delims=" %%E in ('powershell -NoProfile -Command "Write-Output ([char]0x1B)"') do set "ESC=%%E"
if not defined ESC for /f "delims=" %%E in ('echo prompt $E ^| cmd /d /q') do set "ESC=%%E"
exit /b 0

REM ---------------------------------------------------------------------------
REM Same margin idea as bin/menu.py terminal_width: clamp 40..120, width-3
:get_term_width
set "TW=78"
for /f "delims=" %%T in ('powershell -NoProfile -Command "$w = 0; try { $w = [int][Console]::WindowWidth } catch { }; if ($w -lt 40) { $w = 80 }; [Math]::Max(40, [Math]::Min(120, $w - 3))"') do set "TW=%%T"
exit /b 0

REM ---------------------------------------------------------------------------
:draw_menu_frame
set "W="
for /l %%i in (1,1,!TW!) do set "W=!W!="
if "!VT_OK!"=="1" (
  if defined ESC (
    echo !ESC![38;5;118m!W!!ESC![0m
    echo !ESC![35m  XYZ-SCRCPY - Windows dev installer!ESC![0m
    echo !ESC![38;5;118m!W!!ESC![0m
    echo !ESC![38;5;213m  RAINBOWTECHNOLOGY!ESC![0m
    echo !ESC![38;5;118m!W!!ESC![0m
  ) else (
    echo !W!
    echo   XYZ-SCRCPY - Windows dev installer
    echo !W!
    echo   RAINBOWTECHNOLOGY
    echo !W!
  )
) else (
  echo !W!
  echo   XYZ-SCRCPY - Windows dev installer
  echo !W!
  echo   RAINBOWTECHNOLOGY
  echo !W!
)
exit /b 0
