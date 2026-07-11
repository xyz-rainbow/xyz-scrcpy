#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../.venv/bin/python3" ]; then
  exec "$SCRIPT_DIR/../.venv/bin/python3" "$SCRIPT_DIR/launch_with_checks.py" "$@"
elif [ -f "$SCRIPT_DIR/../.venv/bin/python" ]; then
  exec "$SCRIPT_DIR/../.venv/bin/python" "$SCRIPT_DIR/launch_with_checks.py" "$@"
else
  exec python3 "$SCRIPT_DIR/launch_with_checks.py" "$@"
fi
