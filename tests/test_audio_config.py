import unittest
from unittest.mock import patch

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import config_loader  # noqa: E402
import menu  # noqa: E402


class AudioConfigTests(unittest.TestCase):
    def test_defaults_include_audio_target(self):
        cfg = config_loader._normalize_config({})
        self.assertEqual(cfg["audio_target"], "host")
        self.assertEqual(cfg["sound"], "output")

    def test_migrate_sound_off_to_device_target(self):
        cfg = config_loader._normalize_config({"sound": "off"})
        self.assertEqual(cfg["audio_target"], "device")
        self.assertEqual(cfg["sound"], "off")

    def test_migrate_sound_output_to_host_target(self):
        cfg = config_loader._normalize_config({"sound": "output"})
        self.assertEqual(cfg["audio_target"], "host")
        self.assertEqual(cfg["sound"], "output")

    @patch("menu.subprocess.Popen")
    def test_launch_scrcpy_host_does_not_add_no_audio(self, mock_popen):
        menu.launch_scrcpy("ABC123", "host")
        args = mock_popen.call_args[0][0]
        self.assertNotIn("--no-audio", args)

    @patch("menu.subprocess.Popen")
    def test_launch_scrcpy_device_adds_no_audio(self, mock_popen):
        menu.launch_scrcpy("ABC123", "device")
        args = mock_popen.call_args[0][0]
        self.assertIn("--no-audio", args)


if __name__ == "__main__":
    unittest.main()
