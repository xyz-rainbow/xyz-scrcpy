"""PATH backup file restore (mocked registry writes)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import win_path_shim as wps


class RollbackTests(unittest.TestCase):
    def test_restore_user_path_from_backup_calls_write_and_broadcast(self):
        with tempfile.TemporaryDirectory() as td:
            bf = Path(td) / ".path_backup.json"
            bf.write_text(
                json.dumps({"path": "C:\\\\a;D:\\\\b", "reg_type": 2}),
                encoding="utf-8",
            )
            mock_write = MagicMock()
            mock_broadcast = MagicMock()
            with (
                patch.object(wps, "is_windows", return_value=True),
                patch.object(wps, "write_user_path_value", mock_write),
                patch.object(wps, "broadcast_environment_change", mock_broadcast),
            ):
                ok = wps.restore_user_path_from_backup(bf)
            self.assertTrue(ok)
            mock_write.assert_called_once()
            args = mock_write.call_args[0]
            self.assertIn("C:", args[0])
            mock_broadcast.assert_called_once()

    def test_restore_missing_file(self):
        self.assertFalse(wps.restore_user_path_from_backup(Path(tempfile.gettempdir()) / "xyz_scrcpy_no_backup_xyz.json"))


if __name__ == "__main__":
    unittest.main()
