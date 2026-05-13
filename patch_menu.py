import os
import re
import sys
from pathlib import Path

def patch_menu():
    """Deprecated: ``bin/menu.py`` is the single cross-platform source; this script is a no-op."""
    print(
        "patch_menu.py is deprecated and does nothing. "
        "Windows compatibility lives in bin/menu.py upstream."
    )
    return
    base_dir = Path(__file__).parent
    menu_path = base_dir / "bin" / "menu.py"
    if not menu_path.exists():
        print(f"menu.py not found at {menu_path}")
        return

    text = menu_path.read_text(encoding="utf-8")

    # Only patch if not already patched
    if "import msvcrt" in text:
        print("Already patched.")
        return

    # 1. Patch imports
    text = text.replace("import fcntl", "try:\n    import fcntl\nexcept ImportError:\n    fcntl = None")
    text = text.replace("import termios", "try:\n    import termios\nexcept ImportError:\n    termios = None")
    text = text.replace("import tty", "try:\n    import tty\nexcept ImportError:\n    tty = None")

    # 2. Patch LOCK_PATH
    text = text.replace('LOCK_PATH = "/tmp/xyz_menu.lock"', 'import tempfile\nLOCK_PATH = os.path.join(tempfile.gettempdir(), "xyz_menu.lock")')

    # 3. Patch SCRCPY_VENDOR_BIN
    text = text.replace('SCRCPY_VENDOR_BIN = ROOT_DIR / "vendor" / "scrcpy"', 'SCRCPY_VENDOR_BIN = ROOT_DIR / "vendor" / ("scrcpy.exe" if os.name == "nt" else "scrcpy")')

    # 4. Patch get_key()
    original_get_key = """def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch != "\\x1b":
            return ch

        seq = ch
        ready, _, _ = select.select([sys.stdin], [], [], ESCAPE_READ_TIMEOUT)
        if not ready:
            return "\\x1b"
        seq += sys.stdin.read(1)
        ready, _, _ = select.select([sys.stdin], [], [], ESCAPE_READ_TIMEOUT)
        if ready:
            seq += sys.stdin.read(1)
        return seq
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)"""

    new_get_key = """def get_key():
    if os.name != 'nt':
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch != "\\x1b":
                return ch

            seq = ch
            ready, _, _ = select.select([sys.stdin], [], [], ESCAPE_READ_TIMEOUT)
            if not ready:
                return "\\x1b"
            seq += sys.stdin.read(1)
            ready, _, _ = select.select([sys.stdin], [], [], ESCAPE_READ_TIMEOUT)
            if ready:
                seq += sys.stdin.read(1)
            return seq
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    else:
        import msvcrt
        ch = msvcrt.getch()
        if ch == b'\\xe0':
            ch2 = msvcrt.getch()
            if ch2 == b'H': return "\\x1b[A"
            if ch2 == b'P': return "\\x1b[B"
            if ch2 == b'M': return "\\x1b[C"
            if ch2 == b'K': return "\\x1b[D"
        if ch == b'\\r': return "\\r"
        try:
            return ch.decode('utf-8')
        except:
            return ch.decode('latin-1')"""
    text = text.replace(original_get_key, new_get_key)

    # 5. Patch os.system("clear")
    text = text.replace('os.system("clear")', 'os.system("cls" if os.name == "nt" else "clear")')

    # 6. Patch SIGWINCH
    text = text.replace('signal.signal(signal.SIGWINCH, lambda *_: None)', 'if hasattr(signal, "SIGWINCH"):\n        signal.signal(signal.SIGWINCH, lambda *_: None)')

    # 7. Patch fcntl.flock
    text = text.replace('fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)', 'if fcntl:\n            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)')

    # 8. Patch os.remove(LOCK_PATH)
    old_remove = "            os.remove(LOCK_PATH)"
    new_remove = "            try:\n                lock_file.close()\n            except:\n                pass\n            try:\n                os.remove(LOCK_PATH)\n            except OSError:\n                pass"
    text = text.replace(old_remove, new_remove)

    menu_path.write_text(text, encoding="utf-8")
    print("Patched successfully.")

if __name__ == "__main__":
    patch_menu()
