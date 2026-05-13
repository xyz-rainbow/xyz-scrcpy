"""Marker JSON read/write with isolated paths."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import win_path_shim as wps


class MarkerTests(unittest.TestCase):
    def test_write_read_delete_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "shimroot"
            root.mkdir()

            def fake_root():
                return root

            with patch.object(wps, "windows_shim_root", fake_root):
                self.assertIsNone(wps.read_marker())
                wps.write_marker({"alias": "foo", "path_segment": "C:\\x"})
                data = wps.read_marker()
                self.assertEqual(data["alias"], "foo")
                wps.delete_marker()
                self.assertIsNone(wps.read_marker())

    def test_read_marker_corrupt_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "shimroot"
            root.mkdir()
            (root / wps.MARKER_FILENAME).write_text("not-json{{{", encoding="utf-8")

            def fake_root():
                return root

            with patch.object(wps, "windows_shim_root", fake_root):
                self.assertIsNone(wps.read_marker())


if __name__ == "__main__":
    unittest.main()
