# Optional smoke: compile Inno script when ISCC.exe is installed (exit 0 if skipped).
$ErrorActionPreference = "Stop"
$iss = Join-Path $PSScriptRoot "setup.iss"
$candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "[smoke-iscc] ISCC.exe not found; skip (install Inno Setup 6 to compile)."
    exit 0
}
Write-Host "[smoke-iscc] Using $iscc"
& $iscc $iss
exit $LASTEXITCODE
