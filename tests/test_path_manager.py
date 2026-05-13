"""Unit tests for PATH segment helpers (cross-platform; no real registry)."""

import os
import tempfile
import unittest
from pathlib import Path

import win_path_shim as wps


class PathKeyCompareTests(unittest.TestCase):
    def test_empty_or_whitespace_returns_empty_key(self):
        self.assertEqual(wps.path_key_for_compare(""), "")
        self.assertEqual(wps.path_key_for_compare("   "), "")

    def test_same_directory_equal_keys(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "Sub" / "Dir"
            p.mkdir(parents=True)
            self.assertEqual(wps.path_key_for_compare(str(p)), wps.path_key_for_compare(str(p.resolve())))

    def test_split_join_roundtrip(self):
        raw = r"C:\a;D:\b;;C:\a"
        segs = wps.split_path_segments(raw)
        self.assertEqual(segs, [r"C:\a", r"D:\b", r"C:\a"])
        self.assertEqual(wps.join_path_segments(["x", "y"]), "x;y")
        self.assertEqual(wps.split_path_segments(""), [])

    def test_is_duplicate_segment(self):
        with tempfile.TemporaryDirectory() as td:
            one = str(Path(td) / "x")
            Path(one).mkdir()
            two = str(Path(td) / "x").replace("\\", "/") if os.sep == "\\" else one
            self.assertTrue(wps.is_duplicate_segment(one, [two]))
        self.assertTrue(wps.is_duplicate_segment("  ", []))
        self.assertFalse(wps.is_duplicate_segment(r"C:\unique", [r"D:\other"]))


if __name__ == "__main__":
    unittest.main()
