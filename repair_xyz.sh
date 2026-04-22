#!/bin/bash
# XYZ / Rainbowtechnology - Repair Script (Build Final)
echo "Ejecutando reparación de XYZ / Rainbowtechnology..."
pkill -f "menu.py"
pkill -f "monitor.sh"
rm -f /tmp/xyz_menu.lock

# Verificar sintaxis del binario final
python3 -m py_compile /home/cloud-xyz/Documentos/NEXUS/apps/github/xyz-scrcpy/bin/menu.py
if [ $? -eq 0 ]; then
    echo "Sintaxis OK. Reiniciando servicio..."
    systemctl --user restart scrcpy-auto.service
    echo "Sistema restaurado a estado final. #xyz-rainbowtechnology"
else
    echo "Error de sintaxis detectado. Revisar menu.py."
fi
