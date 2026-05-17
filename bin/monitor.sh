#!/usr/bin/env bash
# __  ____   _______
# \ \/ /\ \ / /__  /
#  \  /  \ V /  / /
#  /  \   | |  / /_
# /_/\_\  |_| /____|
# Thin launcher: monitor logic lives in monitor.py (multi-OS).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PATH="${INSTALL_ROOT}/vendor:${PATH}"
VENV_PY="$INSTALL_ROOT/.venv/bin/python3"
if [[ -x "$VENV_PY" ]]; then
  exec "$VENV_PY" "$SCRIPT_DIR/monitor.py" "$@"
fi
exec python3 "$SCRIPT_DIR/monitor.py" "$@"
