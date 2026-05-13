#!/usr/bin/env bash
# __  ____   _______
# \ \/ /\ \ / /__  /
#  \  /  \ V /  / /
#  /  \   | |  / /_
# /_/\_\  |_| /____|
# Thin launcher: monitor logic lives in monitor.py (multi-OS).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/monitor.py" "$@"
