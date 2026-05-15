# Remove regenerable dev/build caches under the repo root (safe: does not touch .venv unless -IncludeVenv).
param(
    [switch]$IncludeVenv,
    [switch]$IncludeDist
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $root "pyproject.toml"))) {
    Write-Error "Run from repo: scripts/clean_dev.ps1 (pyproject.toml not found above scripts/)."
}
Set-Location -LiteralPath $root
Write-Host "[clean_dev] Root: $root"

Get-ChildItem -LiteralPath $root -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[clean_dev] Removed $($_.FullName)"
}
Get-ChildItem -LiteralPath $root -Recurse -Directory -Filter .pytest_cache -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[clean_dev] Removed $($_.FullName)"
}
Get-ChildItem -LiteralPath $root -Recurse -Directory -Filter .mypy_cache -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[clean_dev] Removed $($_.FullName)"
}
Get-ChildItem -LiteralPath $root -Recurse -Directory -Filter .ruff_cache -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "[clean_dev] Removed $($_.FullName)"
}
if ($IncludeDist) {
    $d = Join-Path $root "dist"
    if (Test-Path -LiteralPath $d) {
        Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[clean_dev] Removed dist/"
    }
}
if ($IncludeVenv) {
    $v = Join-Path $root ".venv"
    if (Test-Path -LiteralPath $v) {
        Remove-Item -LiteralPath $v -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[clean_dev] Removed .venv/"
    }
}
Write-Host "[clean_dev] Done."
