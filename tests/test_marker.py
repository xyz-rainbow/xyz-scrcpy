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
                wps.write_marker({"alias": "foo", "path_segment": "C:\\x", "shim_content_hash": "sha256:abc"})
                data = wps.read_marker()
                self.assertEqual(data["alias"], "foo")
                self.assertEqual(data.get("shim_content_hash"), "sha256:abc")
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

    def test_shim_hash_matches_disk(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "shimroot"
            cli = root / "cli"
            root.mkdir()
            cli.mkdir()
            inst = Path(td) / "app"
            (inst / ".venv" / "Scripts").mkdir(parents=True)
            (inst / "bin").mkdir(parents=True)
            (inst / ".venv" / "Scripts" / "python.exe").write_bytes(b"")
            (inst / "bin" / "launch_with_checks.py").write_text("#\n", encoding="utf-8")

            def fake_root():
                return root

            with patch.object(wps, "windows_shim_root", fake_root):
                h, _ = wps.write_cli_shim_pair(cli, "foo", inst)
                wps.write_marker({"alias": "foo", "shim_content_hash": h})
                ok, _detail = wps.shim_hash_matches_disk(wps.read_marker())
                self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
