import subprocess
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import install_xyz

class TestRunCmdErrors(unittest.TestCase):
    def test_run_cmd_raises_on_failure(self):
        """Test that run_cmd raises CalledProcessError when check=True and command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["false"])
            with self.assertRaises(subprocess.CalledProcessError):
                install_xyz.run_cmd(["false"], check=True)

    def test_ensure_linux_runtime_uv_failure(self):
        """Test that ensure_linux_runtime catches CalledProcessError when uv fails."""
        def mock_which(name):
            if name == "uv":
                return "/usr/bin/uv"
            if name == "python3":
                return "/usr/bin/python3"
            return None

        with (
            patch("install_xyz.shutil.which", side_effect=mock_which),
            patch("pathlib.Path.is_file", return_value=True),
            patch("install_xyz.run_cmd") as mock_run_cmd,
            patch("install_xyz._python_has_pip", return_value=False),
            patch("sys.stdout", new=StringIO()) as fake_out,
            patch("install_xyz.wps.log_install_line")
        ):
            mock_run_cmd.side_effect = subprocess.CalledProcessError(1, ["uv", "venv"])

            install_dir = Path("/tmp/fake_install")
            result = install_xyz.ensure_linux_runtime(install_dir)

            output = fake_out.getvalue()
            self.assertIn("[WARN] uv venv/pip failed", output)
            self.assertEqual(result.method, "failed")

    def test_install_service_linux_systemctl_failure(self):
        """Test that install_service handles systemctl failure on Linux."""
        with (
            patch("install_xyz.shutil.which", return_value="/usr/bin/systemctl"),
            patch("install_xyz.run_cmd") as mock_run_cmd,
            patch("sys.stdout", new=StringIO()) as fake_out,
            patch("install_xyz.wps.log_install_line"),
            patch("install_xyz.linux_service_content", return_value="[Unit]..."),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text")
        ):
            mock_run_cmd.side_effect = subprocess.CalledProcessError(1, ["systemctl", "daemon-reload"])

            service_file = Path("/tmp/fake.service")
            install_dir = Path("/tmp/fake_install")

            install_xyz.install_service("linux", service_file, install_dir, enable_service=True)

            output = fake_out.getvalue()
            self.assertIn("[WARN] systemctl --user failed", output)

    def test_install_service_windows_schtasks_failure(self):
        """Test that install_service handles schtasks failure on Windows."""
        with (
            patch("install_xyz.shutil.which", side_effect=lambda x: "/usr/bin/schtasks" if "schtasks" in x else None),
            patch("install_xyz.run_cmd") as mock_run_cmd,
            patch("sys.stdout", new=StringIO()) as fake_out,
            patch("install_xyz.wps.log_install_line"),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text")
        ):
            mock_run_cmd.side_effect = subprocess.CalledProcessError(1, ["schtasks", "/create"])

            service_file = Path("C:/fake.task")
            install_dir = Path("C:/fake_install")

            install_xyz.install_service("windows", service_file, install_dir, enable_service=True)

            output = fake_out.getvalue()
            self.assertIn("[WARN] schtasks /create failed", output)

if __name__ == "__main__":
    unittest.main()
