"""Unit tests for win_path_shim discovery, logging, and registry backup/restore."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import win_path_shim as wps


class WinPathShimGeneralTests(unittest.TestCase):
    def test_is_windows(self):
        self.assertIsInstance(wps.is_windows(), bool)

    def test_path_discovery_roots(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": "/fake/la"}):
            self.assertEqual(wps.windows_shim_root(), Path("/fake/la") / wps.APP_NAME)

        with patch.dict(os.environ, {}, clear=True):
            with patch("win_path_shim.Path.home", return_value=Path("/fake/home")):
                self.assertEqual(
                    wps.windows_shim_root(),
                    Path("/fake/home") / "AppData" / "Local" / wps.APP_NAME,
                )

    def test_shim_subpaths(self):
        root = Path("/fake/root")
        with patch.object(wps, "windows_shim_root", return_value=root):
            self.assertEqual(wps.windows_shim_dir(), root / "cli")
            self.assertEqual(wps.windows_marker_path(), root / wps.MARKER_FILENAME)
            self.assertEqual(wps.windows_path_backup_path(), root / wps.BACKUP_FILENAME)

    def test_windows_temp_dir(self):
        with patch.dict(os.environ, {"TEMP": "/fake/temp"}):
            self.assertEqual(wps.windows_temp_dir(), Path("/fake/temp"))
        with patch.dict(os.environ, {"TMP": "/fake/tmp"}, clear=True):
            self.assertEqual(wps.windows_temp_dir(), Path("/fake/tmp"))
        with patch.dict(os.environ, {}, clear=True):
            with patch("tempfile.gettempdir", return_value="/sys/temp"):
                self.assertEqual(wps.windows_temp_dir(), Path("/sys/temp"))

    def test_log_paths(self):
        inst = Path("/app")
        self.assertEqual(wps.install_log_path(inst), inst / "config" / "install.log")
        self.assertEqual(wps.path_changes_log_path(inst), inst / "config" / "path_changes.log")


class WinregBackupRestoreTests(unittest.TestCase):
    def test_backup_user_path_to_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            backup_file = Path(td) / "backup.json"
            with patch.object(wps, "read_user_path_value", return_value=("C:\\Path", 2)):
                wps.backup_user_path_to_file(backup_file)
                self.assertTrue(backup_file.is_file())
                data = json.loads(backup_file.read_text(encoding="utf-8"))
                self.assertEqual(data["path"], "C:\\Path")
                self.assertEqual(data["reg_type"], 2)

    def test_restore_user_path_from_backup(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            backup_file = Path(td) / "backup.json"
            backup_file.write_text(json.dumps({"path": "C:\\OldPath", "reg_type": 2}), encoding="utf-8")

            with (
                patch.object(wps, "write_user_path_value") as mock_write,
                patch.object(wps, "broadcast_environment_change") as mock_broadcast,
            ):
                res = wps.restore_user_path_from_backup(backup_file)
                self.assertTrue(res)
                mock_write.assert_called_once_with("C:\\OldPath", 2)
                mock_broadcast.assert_called_once()


class LoggingUtilsTests(unittest.TestCase):
    def test_append_path_log(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            log_file = Path(td) / "path.log"
            wps._append_path_log(log_file, "Line 1")
            self.assertEqual(log_file.read_text(encoding="utf-8").strip(), "Line 1")
            wps._append_path_log(log_file, "Line 2")
            self.assertIn("Line 2", log_file.read_text(encoding="utf-8"))

    def test_append_path_log_rotation(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            log_file = Path(td) / "path.log"
            log_file.write_text("X" * (wps.PATH_LOG_MAX_BYTES + 1), encoding="utf-8")
            wps._append_path_log(log_file, "New line")

            self.assertTrue((Path(td) / "path.log.old").is_file())
            self.assertEqual(log_file.read_text(encoding="utf-8").strip(), "New line")

    def test_rotate_install_log(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            log_file = Path(td) / "install.log"
            log_file.write_text("X" * (wps.PATH_LOG_MAX_BYTES + 1), encoding="utf-8")
            wps.rotate_install_log(log_file)
            self.assertTrue((Path(td) / "install.log.old").is_file())
            self.assertFalse(log_file.exists())

    def test_log_install_line(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            inst = Path(td) / "app"
            inst.mkdir()
            wps.log_install_line(inst, "Hello install")
            log_file = wps.install_log_path(inst)
            self.assertTrue(log_file.is_file())
            self.assertIn("Hello install", log_file.read_text(encoding="utf-8"))


class PathManipulationTests(unittest.TestCase):
    def test_remove_segment_from_user_path(self):
        path_val = r"C:\foo;C:\bar;C:\baz"
        with (
            patch.object(wps, "is_windows", return_value=True),
            patch.object(wps, "read_user_path_value", return_value=(path_val, 2)),
            patch.object(wps, "write_user_path_value") as mock_write,
            patch.object(wps, "broadcast_environment_change"),
            patch.object(wps, "path_key_for_compare", side_effect=lambda x: x.lower()),
        ):
            n = wps.remove_segment_from_user_path(r"C:\bar")
            self.assertEqual(n, 1)
            mock_write.assert_called_once_with(r"C:\foo;C:\baz", 2)

    def test_remove_segment_non_windows_returns_zero(self):
        with patch.object(wps, "is_windows", return_value=False):
            self.assertEqual(wps.remove_segment_from_user_path("anything"), 0)


if __name__ == "__main__":
    unittest.main()
