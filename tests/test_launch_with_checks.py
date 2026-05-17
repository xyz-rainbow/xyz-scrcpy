"""Launcher flow tests (no GUI)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BIN = Path(__file__).resolve().parent.parent / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

import launch_with_checks as lwc  # noqa: E402


class LaunchWithChecksFlowTests(unittest.TestCase):
    def test_no_detached_when_already_in_launcher_window(self):
        with patch.dict(os.environ, {"XYZ_LAUNCHER_WINDOW": "1"}, clear=False):
            self.assertFalse(lwc._should_spawn_detached_gui_terminal())

    def test_no_detached_when_stdin_is_tty(self):
        with patch.object(lwc.sys.stdin, "isatty", return_value=True):
            with patch.dict(os.environ, {}, clear=True):
                os.environ.pop("XYZ_LAUNCHER_WINDOW", None)
                self.assertFalse(lwc._should_spawn_detached_gui_terminal())

    def test_detached_when_no_tty_on_linux(self):
        with patch.object(lwc.platform, "system", return_value="Linux"):
            with patch.object(lwc.sys.stdin, "isatty", return_value=False):
                with patch.dict(os.environ, {}, clear=True):
                    self.assertTrue(lwc._should_spawn_detached_gui_terminal())


if __name__ == "__main__":
    unittest.main()
