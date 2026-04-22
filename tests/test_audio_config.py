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
        self.assertFalse(cfg["active_recall"])
        self.assertFalse(cfg["microphone_bus"])

    def test_migrate_sound_off_to_device_target(self):
        cfg = config_loader._normalize_config({"sound": "off"})
        self.assertEqual(cfg["audio_target"], "device")
        self.assertEqual(cfg["sound"], "off")

    def test_migrate_sound_output_to_host_target(self):
        cfg = config_loader._normalize_config({"sound": "output"})
        self.assertEqual(cfg["audio_target"], "host")
        self.assertEqual(cfg["sound"], "output")

    def test_normalize_audio_preferences_forces_host_when_active_recall(self):
        cfg = menu.normalize_audio_preferences({"audio_target": "device", "active_recall": True})
        self.assertEqual(cfg["audio_target"], "host")

    @patch("menu.ensure_microphone_bus")
    @patch("menu.scrcpy_supports_microphone", return_value=False)
    @patch("menu.subprocess.Popen")
    def test_launch_scrcpy_host_does_not_add_no_audio(self, mock_popen, _mic_support, _bus):
        menu.launch_scrcpy("ABC123", {"audio_target": "host", "active_recall": False, "microphone_bus": False})
        args = mock_popen.call_args[0][0]
        self.assertNotIn("--no-audio", args)

    @patch("menu.ensure_microphone_bus")
    @patch("menu.scrcpy_supports_microphone", return_value=False)
    @patch("menu.subprocess.Popen")
    def test_launch_scrcpy_device_adds_no_audio(self, mock_popen, _mic_support, _bus):
        menu.launch_scrcpy("ABC123", {"audio_target": "device", "active_recall": False, "microphone_bus": False})
        args = mock_popen.call_args[0][0]
        self.assertIn("--no-audio", args)

    @patch("menu.ensure_microphone_bus")
    @patch("menu.scrcpy_supports_microphone", return_value=True)
    @patch("menu.subprocess.Popen")
    def test_launch_scrcpy_forces_host_when_active_recall_on(self, mock_popen, _mic_support, _bus):
        menu.launch_scrcpy("ABC123", {"audio_target": "device", "active_recall": True, "microphone_bus": False})
        args = mock_popen.call_args[0][0]
        self.assertNotIn("--no-audio", args)
        self.assertIn("--audio-source=mic", args)

    @patch("menu.ensure_microphone_bus")
    @patch("menu.scrcpy_supports_microphone", return_value=True)
    @patch("menu.subprocess.Popen")
    def test_launch_scrcpy_adds_mic_flag_when_supported(self, mock_popen, _mic_support, _bus):
        menu.launch_scrcpy("ABC123", {"audio_target": "host", "active_recall": True, "microphone_bus": False})
        args = mock_popen.call_args[0][0]
        self.assertIn("--audio-source=mic", args)

    @patch("menu.ensure_microphone_bus")
    @patch("menu.scrcpy_supports_microphone", return_value=False)
    @patch("menu.subprocess.Popen")
    def test_launch_scrcpy_skips_mic_flag_when_unsupported(self, mock_popen, _mic_support, _bus):
        menu.launch_scrcpy("ABC123", {"audio_target": "host", "active_recall": True, "microphone_bus": False})
        args = mock_popen.call_args[0][0]
        self.assertNotIn("--audio-source=mic", args)

    @patch("menu.ensure_microphone_bus", return_value=True)
    @patch("menu.scrcpy_supports_microphone", return_value=False)
    @patch("menu.subprocess.Popen")
    def test_launch_scrcpy_uses_default_env_when_bus_ready(self, mock_popen, _mic_support, _bus):
        menu.launch_scrcpy("ABC123", {"audio_target": "host", "active_recall": False, "microphone_bus": True})
        env = mock_popen.call_args.kwargs["env"]
        self.assertNotIn("PULSE_SINK", env)


if __name__ == "__main__":
    unittest.main()
