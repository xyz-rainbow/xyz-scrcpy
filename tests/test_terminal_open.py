"""Unit tests for bin/terminal_open.py (no real GUI)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import from bin/
import sys

BIN = Path(__file__).resolve().parent.parent / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

import terminal_open as to  # noqa: E402


class ProbeGraphicalSessionTests(unittest.TestCase):
    @patch("terminal_open.platform.system", return_value="Linux")
    def test_linux_missing_display(self, _sys):
        with patch.dict(os.environ, {}, clear=True):
            ok, reason = to.probe_graphical_session()
        self.assertFalse(ok)
        self.assertIn("no_display", reason)

    @patch("terminal_open.platform.system", return_value="Windows")
    def test_windows_always_ok(self, _sys):
        ok, reason = to.probe_graphical_session()
        self.assertTrue(ok)
        self.assertEqual(reason, "")


class OpenCommandInTerminalTests(unittest.TestCase):
    @patch("terminal_open.subprocess.Popen")
    @patch("terminal_open.shutil.which")
    @patch("terminal_open.platform.system", return_value="Linux")
    @patch("terminal_open.probe_graphical_session", return_value=(True, ""))
    def test_linux_uses_first_available_emulator(self, _probe, _plat, which, popen):
        which.side_effect = lambda name: "/usr/bin/gnome-terminal" if name == "gnome-terminal" else None

        with tempfile.TemporaryDirectory() as td:
            result = to.open_command_in_terminal(
                argv=["/usr/bin/python3", str(Path(td) / "script.py")],
                cwd=Path(td),
                title="Test",
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.method, "gnome-terminal")
        self.assertIn("gnome-terminal", result.tried)
        popen.assert_called_once()
        kwargs = popen.call_args[1]
        self.assertTrue(kwargs.get("start_new_session"))

    @patch("terminal_open.shutil.which", return_value=None)
    @patch("terminal_open.platform.system", return_value="Linux")
    @patch("terminal_open.probe_graphical_session", return_value=(True, ""))
    def test_linux_no_emulator(self, _probe, _plat, _which):
        with tempfile.TemporaryDirectory() as td:
            result = to.open_command_in_terminal(
                argv=["python3", "x.py"],
                cwd=Path(td),
            )
        self.assertFalse(result.ok)
        self.assertIn("no_terminal_emulator", result.reason)
        self.assertTrue(result.tried)

    @patch("terminal_open.subprocess.Popen")
    @patch("terminal_open.platform.system", return_value="Windows")
    def test_windows_create_new_console(self, _plat, popen):
        with tempfile.TemporaryDirectory() as td:
            result = to.open_command_in_terminal(
                argv=["python.exe", "menu.py"],
                cwd=Path(td),
            )
        self.assertTrue(result.ok)
        self.assertEqual(result.method, "windows_console")
        flags = popen.call_args[1].get("creationflags", 0)
        create_new = getattr(os, "CREATE_NEW_CONSOLE", 0)
        if create_new:
            self.assertEqual(flags & create_new, create_new)

    @patch("terminal_open.platform.system", return_value="Linux")
    @patch("terminal_open.probe_graphical_session", return_value=(False, "no_display"))
    def test_linux_probe_fails(self, _probe, _plat):
        with tempfile.TemporaryDirectory() as td:
            result = to.open_command_in_terminal(argv=["python3", "a.py"], cwd=Path(td))
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "no_display")


class LinuxSpecsTests(unittest.TestCase):
    def test_paths_with_spaces_quoted_in_xterm_emulator(self):
        specs = to._linux_terminal_specs("80x24", "T", ["/opt/my python/bin/python3", "/path/with spaces/menu.py"])
        xte = next(s for name, s in specs if name == "x-terminal-emulator")
        joined = " ".join(xte)
        self.assertIn("my python", joined)


if __name__ == "__main__":
    unittest.main()
