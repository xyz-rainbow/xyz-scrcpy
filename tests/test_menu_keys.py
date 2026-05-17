"""Tests for menu.get_key() escape / arrow sequence handling."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import menu  # noqa: E402


class MenuKeyHelperTests(unittest.TestCase):
    def test_normalize_ss3_to_csi(self):
        self.assertEqual(menu._normalize_key("\x1bOB"), "\x1b[B")
        self.assertEqual(menu._normalize_key("\x1bOA"), "\x1b[A")
        self.assertEqual(menu._normalize_key("\x1b[B"), "\x1b[B")

    def _pipe_fd_with(self, payload: bytes) -> int:
        fd_r, fd_w = os.pipe()
        os.write(fd_w, payload)
        os.close(fd_w)
        self.addCleanup(lambda: os.close(fd_r) if fd_r >= 0 else None)
        return fd_r

    def test_read_escape_arrow_fast(self):
        fd_r = self._pipe_fd_with(b"[B")
        with patch("menu._stdin_bytes_waiting", return_value=2):
            result = menu._read_escape_sequence("\x1b", fd_r)
        self.assertEqual(result, "\x1b[B")

    def test_read_escape_buffered_after_first_poll_miss(self):
        fd_r = self._pipe_fd_with(b"[B")
        with patch("menu._stdin_bytes_waiting", return_value=2):
            result = menu._read_escape_sequence("\x1b", fd_r)
        self.assertEqual(result, "\x1b[B")

    def test_read_escape_bare_esc(self):
        with patch("menu._stdin_bytes_waiting", return_value=0), patch(
            "menu.select.select",
            return_value=([], [], []),
        ), patch("menu.time.monotonic", side_effect=[0.0, 1.0]):
            result = menu._read_escape_sequence("\x1b", 0)
        self.assertEqual(result, "\x1b")

    def test_read_escape_ss3_down(self):
        fd_r = self._pipe_fd_with(b"OB")
        with patch("menu._stdin_bytes_waiting", return_value=2):
            result = menu._read_escape_sequence("\x1b", fd_r)
        self.assertEqual(result, "\x1b[B")

    def test_read_escape_incomplete_csi_not_bare_esc(self):
        fd_r = self._pipe_fd_with(b"[")
        with patch("menu._stdin_bytes_waiting", return_value=1), patch(
            "menu.select.select",
            return_value=([], [], []),
        ), patch("menu.time.monotonic", side_effect=[0.0, 1.0]):
            result = menu._read_escape_sequence("\x1b", fd_r)
        self.assertEqual(result, "\x1b[")
        self.assertNotEqual(result, "\x1b")


class MenuGetKeyTests(unittest.TestCase):
    @patch("menu.os.name", "posix")
    @patch("menu.tty.setraw")
    @patch("menu.termios.tcsetattr")
    @patch("menu.termios.tcgetattr", return_value=MagicMock())
    @patch("menu.os.read", return_value=b"\x1b")
    @patch("menu._read_escape_sequence", return_value="\x1b[B")
    def test_get_key_delegates_escape_to_reader(self, _mock_read_esc, _os_read, _getattr, _setattr, _setraw):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.fileno.return_value = 0
            result = menu.get_key()
        self.assertEqual(result, "\x1b[B")
        _mock_read_esc.assert_called_once()

    @patch("menu.os.name", "posix")
    @patch("menu.tty.setraw")
    @patch("menu.termios.tcsetattr")
    @patch("menu.termios.tcgetattr", return_value=MagicMock())
    @patch("menu.os.read", return_value=b"q")
    def test_get_key_plain_char(self, _os_read, _getattr, _setattr, _setraw):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.fileno.return_value = 0
            result = menu.get_key()
        self.assertEqual(result, "q")


if __name__ == "__main__":
    unittest.main()
