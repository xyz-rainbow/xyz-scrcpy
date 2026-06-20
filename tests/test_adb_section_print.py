"""Tests for adb_resolve.print_adb_section."""

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import adb_resolve  # noqa: E402


class PrintAdbSectionTests(unittest.TestCase):
    def test_adb_not_found(self):
        with patch("adb_resolve.resolve_adb_executable", return_value=("adb", "not_found")):
            f = io.StringIO()
            with redirect_stdout(f):
                adb_resolve.print_adb_section(Path("/fake/repo"))
            output = f.getvalue()

        self.assertIn("--- adb (Android Debug Bridge) ---", output)
        self.assertIn("resolved_executable: adb", output)
        self.assertIn("resolution_source: not_found", output)
        self.assertIn("adb version: (skipped — no adb on PATH", output)
        self.assertIn("adb devices: (skipped — same reason)", output)

    def test_adb_found_success(self):
        mock_resolve = ("path/to/adb", "PATH")
        mock_version = MagicMock(stdout="Android Debug Bridge version 1.0.41\nVersion 34.0.4-10411341\nInstalled as /usr/lib/android-sdk/platform-tools/adb", stderr="", returncode=0)
        mock_devices = MagicMock(stdout="List of devices attached\n12345678\tdevice\n87654321\tdevice\n", stderr="", returncode=0)

        with (
            patch("adb_resolve.resolve_adb_executable", return_value=mock_resolve),
            patch("adb_resolve.subprocess.run", side_effect=[mock_version, mock_devices])
        ):
            f = io.StringIO()
            with redirect_stdout(f):
                adb_resolve.print_adb_section(Path("/fake/repo"))
            output = f.getvalue()

        self.assertIn("resolved_executable: path/to/adb", output)
        self.assertIn("resolution_source: PATH", output)
        self.assertIn("adb version:", output)
        self.assertIn("  Android Debug Bridge version 1.0.41", output)
        self.assertIn("adb devices:", output)
        self.assertIn("  12345678\tdevice", output)
        self.assertIn("  87654321\tdevice", output)
        self.assertNotIn("hint: no devices listed", output)

    def test_adb_no_devices_hint(self):
        mock_resolve = ("path/to/adb", "PATH")
        mock_version = MagicMock(stdout="adb version 1.0.41", stderr="", returncode=0)
        mock_devices = MagicMock(stdout="List of devices attached\n\n", stderr="", returncode=0)

        with (
            patch("adb_resolve.resolve_adb_executable", return_value=mock_resolve),
            patch("adb_resolve.subprocess.run", side_effect=[mock_version, mock_devices])
        ):
            f = io.StringIO()
            with redirect_stdout(f):
                adb_resolve.print_adb_section(Path("/fake/repo"))
            output = f.getvalue()

        self.assertIn("adb devices:", output)
        self.assertIn("hint: no devices listed", output)

    def test_adb_version_os_error(self):
        mock_resolve = ("path/to/adb", "PATH")

        with (
            patch("adb_resolve.resolve_adb_executable", return_value=mock_resolve),
            patch("adb_resolve.subprocess.run", side_effect=OSError("permission denied"))
        ):
            f = io.StringIO()
            with redirect_stdout(f):
                adb_resolve.print_adb_section(Path("/fake/repo"))
            output = f.getvalue()

        self.assertIn("adb version: (failed to run: permission denied)", output)

    def test_adb_version_timeout(self):
        mock_resolve = ("path/to/adb", "PATH")

        with (
            patch("adb_resolve.resolve_adb_executable", return_value=mock_resolve),
            patch("adb_resolve.subprocess.run", side_effect=subprocess.TimeoutExpired(["adb", "version"], 20))
        ):
            f = io.StringIO()
            with redirect_stdout(f):
                adb_resolve.print_adb_section(Path("/fake/repo"))
            output = f.getvalue()

        self.assertIn("adb version: (failed to run: Command '['adb', 'version']' timed out after 20 seconds)", output)

    def test_adb_devices_non_zero_exit(self):
        mock_resolve = ("path/to/adb", "PATH")
        mock_version = MagicMock(stdout="adb version 1.0.41", stderr="", returncode=0)
        # Empty output but non-zero exit code
        mock_devices = MagicMock(stdout="", stderr="", returncode=1)

        with (
            patch("adb_resolve.resolve_adb_executable", return_value=mock_resolve),
            patch("adb_resolve.subprocess.run", side_effect=[mock_version, mock_devices])
        ):
            f = io.StringIO()
            with redirect_stdout(f):
                adb_resolve.print_adb_section(Path("/fake/repo"))
            output = f.getvalue()

        self.assertIn("adb devices:", output)
        self.assertIn("  (empty output, exit 1)", output)
        self.assertIn("  (exit code 1)", output)
        self.assertIn("hint: no devices listed", output)


if __name__ == "__main__":
    unittest.main()
