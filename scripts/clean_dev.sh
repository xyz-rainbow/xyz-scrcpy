#!/usr/bin/env bash
# Remove regenerable dev/build caches from repo root (does not remove .venv unless CLEAN_VENV=1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "[clean_dev] Root: $ROOT"
find "$ROOT" -depth -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -depth -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -depth -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -depth -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
if [[ "${CLEAN_DIST:-}" == "1" ]] && [[ -d "$ROOT/dist" ]]; then
  rm -rf "$ROOT/dist"
  echo "[clean_dev] Removed dist/"
fi
if [[ "${CLEAN_VENV:-}" == "1" ]] && [[ -d "$ROOT/.venv" ]]; then
  rm -rf "$ROOT/.venv"
  echo "[clean_dev] Removed .venv/"
fi
echo "[clean_dev] Done."
