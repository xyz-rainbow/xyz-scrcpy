"""resolve_python_for_checks with mocked subprocess / which."""

import unittest
from unittest.mock import MagicMock, patch

import win_path_shim as wps


def _run_sequence(returncodes_and_stdout: list[tuple[int, str]]):
    """Build a side_effect for subprocess.run: list of (returncode, stdout)."""

    def _fake(cmd, **kwargs):
        if not returncodes_and_stdout:
            raise AssertionError("unexpected subprocess.run")
        rc, out = returncodes_and_stdout.pop(0)
        m = MagicMock()
        m.returncode = rc
        m.stdout = out
        m.stderr = ""
        return m

    return _fake


class PythonDetectorTests(unittest.TestCase):
    def test_no_candidates(self):
        with patch("win_path_shim.shutil.which", return_value=None):
            exe, err = wps.resolve_python_for_checks()
        self.assertIsNone(exe)
        self.assertIsNotNone(err)

    def test_py_launcher_happy_path(self):
        pyexe = r"C:\Python312\python.exe"
        seq = [
            (0, pyexe + "\n"),
            (0, "3.12\n"),
            (0, ""),
        ]

        def which(name):
            return "py" if name == "py" else None

        with (
            patch("win_path_shim.shutil.which", side_effect=which),
            patch("win_path_shim.subprocess.run", side_effect=_run_sequence(seq)),
        ):
            exe, err = wps.resolve_python_for_checks()
        self.assertEqual(exe, pyexe)
        self.assertIsNone(err)

    def test_rejects_embeddable_without_pip(self):
        pyexe = r"C:\Emb\python.exe"
        seq = [
            (0, pyexe + "\n"),
            (0, "3.12\n"),
            (1, ""),
        ]

        def which(name):
            return "py" if name == "py" else None

        with (
            patch("win_path_shim.shutil.which", side_effect=which),
            patch("win_path_shim.subprocess.run", side_effect=_run_sequence(seq)),
        ):
            exe, err = wps.resolve_python_for_checks()
        self.assertIsNone(exe)
        self.assertIn("pip", (err or "").lower())


if __name__ == "__main__":
    unittest.main()
