"""Tests for bin/alias_sync.py."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import alias_sync  # noqa: E402
import install_xyz  # noqa: E402


class AliasSyncTests(unittest.TestCase):
    def test_sync_command_alias_missing_install_dir(self):
        ok, msg = alias_sync.sync_command_alias("xyz-scrcpy", Path("/nonexistent/path"))
        self.assertFalse(ok)
        self.assertIn("not found", msg.lower())

    def test_prune_managed_launchers_removes_secondary(self):
        with tempfile.TemporaryDirectory() as td:
            install_dir = Path(td) / "app"
            launcher_dir = Path(td) / "bin"
            install_dir.mkdir(parents=True)
            launcher_dir.mkdir(parents=True)
            (install_dir / "bin").mkdir()
            (install_dir / "bin" / "launch_with_checks.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            marker = str(install_dir / "bin" / "launch_with_checks.sh")
            keep = launcher_dir / "xyz-scrcpy"
            stale = launcher_dir / "xyz-android"
            keep.write_text(f"bash \"{marker}\"\n", encoding="utf-8")
            stale.write_text(f"bash \"{marker}\"\n", encoding="utf-8")
            install_xyz.prune_managed_launchers(launcher_dir, install_dir, "linux", "xyz-scrcpy")
            self.assertTrue(keep.exists())
            self.assertFalse(stale.exists())

    @patch("install_xyz.do_sync_alias")
    def test_sync_delegates_to_installer(self, mock_do_sync):
        ok, msg = alias_sync.sync_command_alias("my-alias", ROOT)
        self.assertTrue(ok)
        mock_do_sync.assert_called_once()
        self.assertIn("my-alias", msg)


if __name__ == "__main__":
    unittest.main()
