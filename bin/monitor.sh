#!/usr/bin/env bash
# __  ____   _______
# \ \/ /\ \ / /__  /
#  \  /  \ V /  / /
#  /  \   | |  / /_
# /_/\_\  |_| /____|
# Thin launcher: monitor logic lives in monitor.py (multi-OS).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../.venv/bin/python3" ]; then
  exec "$SCRIPT_DIR/../.venv/bin/python3" "$SCRIPT_DIR/monitor.py" "$@"
elif [ -f "$SCRIPT_DIR/../.venv/bin/python" ]; then
  exec "$SCRIPT_DIR/../.venv/bin/python" "$SCRIPT_DIR/monitor.py" "$@"
else
  exec python3 "$SCRIPT_DIR/monitor.py" "$@"
fi
