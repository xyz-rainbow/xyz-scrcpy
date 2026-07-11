#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ -x "$ROOT/pkg_launchers/unix/installer.sh" ]]; then
  exec "$ROOT/pkg_launchers/unix/installer.sh" "$@"
fi
exec "$ROOT/launchers/unix/installer.sh" "$@"