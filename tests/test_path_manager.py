"""Unit tests for PATH segment helpers (cross-platform; no real registry)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


class WinregPathMockTests(unittest.TestCase):
    """HKCU Path read/write/dedupe with mocked winreg (Linux CI)."""

    def test_add_shim_preserves_reg_expand_sz(self):
        reg_expand_sz = 2
        path_before = r"C:\first;D:\second"
        shim_canonical = r"C:\Shim\cli"

        def fake_read():
            return path_before, reg_expand_sz

        written: list[tuple[str, int]] = []

        def fake_write(val: str, typ: int) -> None:
            written.append((val, typ))

        with (
            patch.object(wps, "is_windows", return_value=True),
            patch.object(wps, "read_user_path_value", side_effect=fake_read),
            patch.object(wps, "write_user_path_value", side_effect=fake_write),
            patch.object(wps, "broadcast_environment_change"),
            patch.object(wps, "_canonical_segment_for_path", return_value=shim_canonical),
        ):
            out = wps.add_shim_dir_to_user_path(Path("ignored"), path_log=None)

        self.assertEqual(out, shim_canonical)
        self.assertEqual(len(written), 1)
        new_val, new_typ = written[0]
        self.assertEqual(new_typ, reg_expand_sz)
        self.assertIn(r"C:\first", new_val)
        self.assertIn(shim_canonical, new_val)
        self.assertTrue(new_val.endswith(shim_canonical) or f";{shim_canonical}" in new_val)

    def test_add_shim_skips_duplicate_preserves_path(self):
        reg_expand_sz = 2
        shim_canonical = r"C:\Shim\cli"
        path_before = rf"C:\first;{shim_canonical}"

        def fake_read():
            return path_before, reg_expand_sz

        written: list[tuple[str, int]] = []

        def fake_write(val: str, typ: int) -> None:
            written.append((val, typ))

        with (
            patch.object(wps, "is_windows", return_value=True),
            patch.object(wps, "read_user_path_value", side_effect=fake_read),
            patch.object(wps, "write_user_path_value", side_effect=fake_write),
            patch.object(wps, "broadcast_environment_change"),
            patch.object(wps, "_canonical_segment_for_path", return_value=shim_canonical),
        ):
            wps.add_shim_dir_to_user_path(Path("ignored"), path_log=None)

        self.assertEqual(written, [])

    def test_count_user_path_shim_segments_mocked(self):
        def keyify(s: str) -> str:
            return {"A": "a", "B": "b", "C": "c"}.get(s, "")

        with (
            patch.object(wps, "is_windows", return_value=True),
            patch.object(wps, "read_user_path_value", return_value=("ignored", 2)),
            patch.object(wps, "split_path_segments", return_value=["A", "B", "C"]),
            patch.object(wps, "path_key_for_compare", side_effect=keyify),
            patch.object(wps, "shim_path_key", return_value="b"),
        ):
            n = wps.count_user_path_shim_segments()
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
