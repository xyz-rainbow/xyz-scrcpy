"""PATH backup file restore (mocked registry writes)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(_ROOT), str(_ROOT / "lib")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from xyz_scrcpy import win_path_shim as wps  # noqa: E402


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
