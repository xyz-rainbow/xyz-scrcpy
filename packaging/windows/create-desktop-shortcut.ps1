# Invoked from Inno [Run] after install_xyz created the Start Menu .cmd (Inno runs [Icons] before [Run], so we create the desktop .lnk here).
param(
    [Parameter(Mandatory = $true)][string]$AppName,
    [Parameter(Mandatory = $true)][string]$Alias,
    [Parameter(Mandatory = $true)][string]$IconPath
)
$ErrorActionPreference = "Stop"
$programs = [Environment]::GetFolderPath("Programs")
$target = Join-Path $programs "$Alias.cmd"
if (-not (Test-Path -LiteralPath $target)) {
    Write-Warning "[create-desktop-shortcut] Target missing: $target"
    exit 0
}
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "$AppName.lnk"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $target
$s.IconLocation = $IconPath
$s.Save()
Write-Host "[create-desktop-shortcut] Wrote $lnk"
