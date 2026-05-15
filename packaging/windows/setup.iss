; Inno Setup 6 — from repo root: "ISCC.exe" packaging\windows\setup.iss
; Requires Python 3.10+ (py -3 or python) on PATH.

#define MyAppName "XYZ-scrcpy"
#define MyAppAlias "xyz-scrcpy"
; Keep in sync with [project] version in pyproject.toml
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Rainbowtechnology"
#define MyAppURL "https://github.com/xyz-rainbow/xyz-scrcpy"
#define MyAppIcon "app.ico"

[Setup]
AppId={{A7B2E9F1-4C3D-5E6F-7890-ABCD12345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\XYZ-scrcpy
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=xyz-scrcpy-setup
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppIcon}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[CustomMessages]
AppReleaseHint=Build the installer with Inno Setup 6 (ISCC.exe). See README section Release / Inno.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "app.ico"; DestDir: "{app}"; Flags: ignoreversion
; Excludes: comma-separated (not semicolons — see Inno [Files] Excludes). Patterns exclude dev/CI trees from the shipped payload.
Source: "..\..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; \
  Excludes: "\.git\*,\.venv\*,\dist\*,__pycache__\*,*.pyc,\.cursor\*,\.pytest_cache\*,\agent-transcripts\*,\.github\*,\scripts\*,packaging\windows\app.ico,config\*.log"

; Do not use [Icons] targeting the Start Menu .cmd here: Inno processes [Icons] before non-postinstall [Run],
; but install_xyz.py creates that .cmd in the first [Run]. Optional desktop .lnk is created in step 2 below.

[Run]
Filename: "{cmd}"; Parameters: "/c set XYZ_INNO_INSTALL=1&& py -3 ""{app}\install_xyz.py"" --action install --yes"; \
  WorkingDir: "{app}"; Flags: waituntilterminated; StatusMsg: "Running Python installer (venv, CLI, Task)..."
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
  Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{app}\packaging\windows\create-desktop-shortcut.ps1"" -AppName ""{#MyAppName}"" -Alias ""{#MyAppAlias}"" -IconPath ""{app}\{#MyAppIcon}"""; \
  WorkingDir: "{app}"; Flags: runhidden waituntilterminated; Tasks: desktopicon; StatusMsg: "Creating desktop shortcut..."
Filename: "{userprograms}\{#MyAppAlias}.cmd"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{userdesktop}\{#MyAppName}.lnk"

[UninstallRun]
; runifexists is not valid for [UninstallRun] in Inno 6; guard with cmd if exist.
Filename: "{cmd}"; Parameters: "/c if exist ""{app}\install_xyz.py"" (set XYZ_INNO_INSTALL=1&& py -3 ""{app}\install_xyz.py"" --action uninstall --yes)"; \
  WorkingDir: "{app}"; Flags: waituntilterminated; RunOnceId: "XyzUninstallPy"

[Code]
function CheckPython310: Boolean;
var
  ec: Integer;
begin
  if Exec(ExpandConstant('{cmd}'), '/c py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)"', '', SW_HIDE, ewWaitUntilTerminated, ec) and (ec = 0) then
  begin
    Result := True;
    Exit;
  end;
  if Exec(ExpandConstant('{cmd}'), '/c python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)"', '', SW_HIDE, ewWaitUntilTerminated, ec) and (ec = 0) then
  begin
    Result := True;
    Exit;
  end;
  MsgBox('Python 3.10+ not found. Install from https://www.python.org/downloads/ (check "Add to PATH") or install the py launcher, then retry.'#13#10#13#10'Unsigned EXEs may show SmartScreen — use More info / Run anyway if you trust this build.'#13#10#13#10'{cm:AppReleaseHint}', mbError, MB_OK);
  Result := False;
end;

function InitializeSetup(): Boolean;
begin
  Result := CheckPython310;
end;

[Messages]
WelcomeLabel1=Welcome to the [name] Setup Wizard
WelcomeLabel2=This copies the application files below, then runs install_xyz.py (Python venv under your profile, CLI PATH shim, scheduled task).#13#10#13#10The uninstaller runs install_xyz.py uninstall first, then removes the files under this folder.
