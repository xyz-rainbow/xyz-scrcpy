#!/usr/bin/env python3
import py_compile
import sys
import os

# Ruta dinámica del repositorio final
REPO_DIR = "/home/cloud-xyz/Documentos/NEXUS/apps/github/xyz-scrcpy"
menu_script = os.path.join(REPO_DIR, "bin/menu.py")

print(f"Verificando integridad de: {menu_script}")

try:
    if not os.path.exists(menu_script):
        print(f"FAIL: Archivo no encontrado en {menu_script}")
        sys.exit(1)
        
    py_compile.compile(menu_script, doraise=True)
    print("✓ OK: Sintaxis perfecta de XYZ / Rainbowtechnology")
    sys.exit(0)
except Exception as e:
    print(f"✗ FAIL: Error de sintaxis detectado")
    print(f"Detalle: {e}")
    sys.exit(1)
