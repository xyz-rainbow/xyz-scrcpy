import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Add the root directory to sys.path to import patch_menu
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import patch_menu

class TestPatchMenu(unittest.TestCase):

    @patch("builtins.print")
    def test_apply_patches_file_not_found(self, mock_print):
        mock_menu_path = MagicMock(spec=Path)
        mock_menu_path.exists.return_value = False

        patch_menu.apply_patches(mock_menu_path)

        # Verify
        mock_print.assert_called_with(f"menu.py not found at {mock_menu_path}")

    @patch("builtins.print")
    def test_apply_patches_already_patched(self, mock_print):
        mock_menu_path = MagicMock(spec=Path)
        mock_menu_path.exists.return_value = True
        mock_menu_path.read_text.return_value = "import msvcrt"

        patch_menu.apply_patches(mock_menu_path)

        # Verify
        mock_print.assert_called_with("Already patched.")
        mock_menu_path.write_text.assert_not_called()

    @patch("builtins.print")
    def test_apply_patches_successful_patch(self, mock_print):
        mock_menu_path = MagicMock(spec=Path)
        mock_menu_path.exists.return_value = True

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

        original_content = f"""
import fcntl
import termios
import tty
LOCK_PATH = "/tmp/xyz_menu.lock"
SCRCPY_VENDOR_BIN = ROOT_DIR / "vendor" / "scrcpy"
{original_get_key}
os.system("clear")
signal.signal(signal.SIGWINCH, lambda *_: None)
fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.remove(LOCK_PATH)
"""
        mock_menu_path.read_text.return_value = original_content

        patch_menu.apply_patches(mock_menu_path)

        # Verify
        mock_print.assert_called_with("Patched successfully.")

        # Check if write_text was called
        mock_menu_path.write_text.assert_called()
        args, kwargs = mock_menu_path.write_text.call_args
        patched_content = args[0]

        self.assertIn("try:\n    import fcntl\nexcept ImportError:\n    fcntl = None", patched_content)
        self.assertIn('import tempfile\nLOCK_PATH = os.path.join(tempfile.gettempdir(), "xyz_menu.lock")', patched_content)
        self.assertIn('os.name != \'nt\'', patched_content)
        self.assertIn('import msvcrt', patched_content)
        self.assertIn('os.system("cls" if os.name == "nt" else "clear")', patched_content)

    @patch("builtins.print")
    def test_patch_menu_is_noop(self, mock_print):
        patch_menu.patch_menu()
        mock_print.assert_called()
        args, _ = mock_print.call_args
        self.assertIn("deprecated", args[0])

if __name__ == "__main__":
    unittest.main()
