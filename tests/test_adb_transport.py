"""Tests for bin/adb_transport.py."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import adb_transport  # noqa: E402


class AdbTransportTests(unittest.TestCase):
    def test_classify_serial(self):
        self.assertEqual(adb_transport.classify_serial("141a98fa"), "usb")
        self.assertEqual(adb_transport.classify_serial("192.168.1.5:5555"), "tcp")

    def test_get_device_ip_from_route(self):
        def fake_run(cmd):
            return True, "192.168.1.10 dev wlan0 src 192.168.1.55", "", 0

        ip, err = adb_transport.get_device_ip("/adb", "serial", fake_run)
        self.assertEqual(ip, "192.168.1.55")
        self.assertEqual(err, "")

    def test_connect_wifi_success(self):
        def fake_run(cmd):
            return True, "connected to 192.168.1.55:5555", "", 0

        ok, serial, msg = adb_transport.connect_wifi("/adb", "192.168.1.55", 5555, fake_run)
        self.assertTrue(ok)
        self.assertEqual(serial, "192.168.1.55:5555")

    def test_enable_tcpip_failure(self):
        def fake_run(cmd):
            return False, "", "error: device offline", 1

        ok, msg = adb_transport.enable_tcpip("/adb", "serial", 5555, fake_run)
        self.assertFalse(ok)
        self.assertIn("offline", msg)


if __name__ == "__main__":
    unittest.main()
