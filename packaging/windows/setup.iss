; Inno Setup 6 — from repo root: "ISCC.exe" packaging\windows\setup.iss
; Requires Python 3.10+ (py -3 or python) on PATH.

#define MyAppName "XYZ-scrcpy"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Rainbowtechnology"
#define MyAppURL "https://github.com/xyz-rainbow/xyz-scrcpy"

[Setup]
AppId={{A7B2E9F1-4C3D-5E6F-7890-ABCD12345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\xyz-scrcpy-setup-staging
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=xyz-scrcpy-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; \
  Excludes: "\.git\*;\.venv\*;dist\*;__pycache__\*;*.pyc;\.cursor\*;agent-transcripts\*"

[Run]
Filename: "{cmd}"; Parameters: "/c py -3 ""{app}\install_xyz.py"" --action install --yes"; \
  WorkingDir: "{app}"; Flags: waituntilterminated; StatusMsg: "Running Python installer..."

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c py -3 ""{app}\install_xyz.py"" --action uninstall --yes"; \
  WorkingDir: "{app}"; Flags: waituntilterminated runifexists; RunOnceId: "XyzUninstallPy"

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
  MsgBox('Python 3.10+ not found. Install from https://www.python.org/downloads/ (check "Add to PATH") or install the py launcher, then retry.'#13#10#13#10'Unsigned EXEs may show SmartScreen — use More info / Run anyway if you trust this build.', mbError, MB_OK);
  Result := False;
end;

function InitializeSetup(): Boolean;
begin
  Result := CheckPython310;
end;

[Messages]
WelcomeLabel1=Welcome to the [name] Setup Wizard
WelcomeLabel2=This extracts the app to a staging folder, then runs install_xyz.py (profile copy, CLI PATH shim, scheduled task). Uninstall runs install_xyz.py uninstall before removing staging files.
