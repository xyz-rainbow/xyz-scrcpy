#!/bin/bash
# __  ____   _______
# \ \/ /\ \ / /__  /
#  \  /  \ V /  / / 
#  /  \   | |  / /_ 
# /_/\_\  |_| /____|
# #xyz-rainbowtechnology

REPO_DIR="/home/cloud-xyz/Documentos/NEXUS/apps/github/xyz-scrcpy"
TEST_SCRIPT="$REPO_DIR/bin/test_syntax.py"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          XYZ / RAINBOWTECHNOLOGY - REPAIR SYSTEM           ║"
echo "╚════════════════════════════════════════════════════════════╝"

echo "[1/3] Limpiando procesos y bloqueos..."
pkill -f "menu.py"
pkill -f "monitor.sh"
rm -f /tmp/xyz_menu.lock
rm -f /tmp/xyz_monitor.pid
sleep 1

echo "[2/3] Validando integridad del código..."
python3 "$TEST_SCRIPT"

if [ $? -eq 0 ]; then
    echo "[3/3] Reiniciando servicios..."
    systemctl --user daemon-reload
    systemctl --user restart scrcpy-auto.service
    echo "✓ Sistema restaurado con éxito. #xyz-rainbowtechnology"
else
    echo "✗ ERROR: No se puede reiniciar el servicio debido a fallos en el código."
    exit 1
fi
