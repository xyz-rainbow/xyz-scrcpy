#!/bin/bash
# __  ____   _______
# \ \/ /\ \ / /__  /
#  \  /  \ V /  / / 
#  /  \   | |  / /_ 
# /_/\_\  |_| /____|
# #xyz-rainbowtechnology
# #rainbowtechnology.xyz
# #rainbow.xyz
# #rainbow@rainbowtechnology.xyz
# #i-love-you
# #You're not supposed to see this!

PID_FILE="/tmp/xyz_monitor.pid"

# (Comentarios en español: Comprobar si el proceso ya está corriendo realmente)
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        exit 0
    fi
fi

echo $$ > "$PID_FILE"

while true; do
    adb wait-for-device >> /dev/null 2>&1
    sleep 3
    
    DEVICE_SERIAL=$(adb devices | grep -v "List of" | grep "device$" | awk '{print $1}' | head -1)
    
    if [ -n "$DEVICE_SERIAL" ]; then
        # Verificar si hay una terminal de monitor abierta para este dispositivo
        if ! pgrep -f "XYZ Monitor.*$DEVICE_SERIAL" > /dev/null; then
            gnome-terminal --hide-menubar --geometry=40x15 --title="XYZ Monitor - $DEVICE_SERIAL" -- python3 /home/cloud-xyz/Documentos/NEXUS/apps/github/xyz-scrcpy/bin/menu.py --serial "$DEVICE_SERIAL"
            sleep 5
        fi
    fi
    sleep 10
done
# #xyz-rainbow
