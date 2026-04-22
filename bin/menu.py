#!/usr/bin/env python3
import subprocess, sys, os, tty, termios, re, fcntl

BRAND_NAME = "RAINBOWTECHNOLOGY"
ASCII_ART = [
    r"  __  ____   _______",
    r"  \ \/ /\ \ / /__  /",
    r"   \  /  \ V /  / / ",
    r"   /  \   | |  / /_ ",
    r"  /_/\_\  |_| /____|"
]

# Colores ANSI
RED, GREEN, MAGENTA, ORANGE, WHITE, RESET = "\033[91m", "\033[38;5;118m", "\033[35m", "\033[38;5;208m", "\033[37m", "\033[0m"

def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b': ch += sys.stdin.read(2)
        return ch
    finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)

def get_devices():
    try:
        out = subprocess.check_output(["adb", "devices"]).decode().splitlines()
        serials = [l.split()[0] for l in out if "device" in l and not l.startswith("List")]
        return [f"{subprocess.check_output(['adb', '-s', s, 'shell', 'getprop', 'ro.product.model']).decode().strip()} ({s})" for s in serials]
    except: return []

def main():
    lock_file = open('/tmp/xyz_menu.lock', 'w')
    try: fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB) 
    except: sys.exit(0)

    idx = 0
    w = 42 # Ancho base para centrado
    border = "=" * w
    while True:
        os.system('clear')
        out = [f"{'{[SPACE] [ENTER] [ESC]}'.center(w)}", f"{RED}{border}{RESET}", ""]
        for line in ASCII_ART: out.append(f"{GREEN}{line.center(w)}{RESET}")
        
        devs = get_devices()
        opts = devs + ["SETTINGS", "EXIT"]
        out.append("")
        for i, opt in enumerate(opts):
            if i == idx:
                if "(" in opt:
                    m, s = opt.split(' (')
                    # Texto seleccionado centrado con flechas simétricas
                    line = f"> {ORANGE}{m} {WHITE}({s.replace(')', '')}){RESET} <"
                    # Ajuste de espacio para compensar caracteres ANSI invisibles en center()
                    out.append(line.center(w + 24)) 
                else:
                    line = f"> {opt} <"
                    out.append(line.center(w + 8))
            else:
                out.append(opt.center(w))
            
        out.append(f"\n{GREEN}{border}{RESET}")
        out.append(f"{MAGENTA}{BRAND_NAME.center(w)}{RESET}")
        out.append(f"{GREEN}{border}{RESET}")

        sys.stdout.write("\n".join(out))
        sys.stdout.flush()

        key = get_key()
        if key == '\x1b[A': idx = (idx - 1) % len(opts)
        elif key == '\x1b[B': idx = (idx + 1) % len(opts)
        elif key == '\r':
            sel = opts[idx]
            if sel == "EXIT": break
            elif sel != "SETTINGS": 
                match = re.search(r"\((.*?)\)", sel)
                subprocess.Popen(["scrcpy", "-s", match.group(1) if match else sel, "--render-driver=software"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif key == '\x1b': break
    
    if os.path.exists('/tmp/xyz_menu.lock'): os.remove('/tmp/xyz_menu.lock')
    os.system('clear')

if __name__ == "__main__":
    main()
# #xyz-rainbowtechnology
