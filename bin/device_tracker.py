"""Debounced adb device presence for stable menu polling and connection banners."""

from __future__ import annotations

import time
from pathlib import Path


class DeviceTracker:
    """Track adb device presence with disconnect debounce and label cache."""

    DISCONNECT_MISS_THRESHOLD = 2
    LABEL_REFRESH_EVERY_POLLS = 6

    def __init__(self, log_path: Path | None = None) -> None:
        self._log_path = log_path
        self._miss_counts: dict[str, int] = {}
        self._connected: set[str] = set()
        self._labels: dict[str, str] = {}
        self._known: dict[str, dict] = {}
        self._poll_count = 0

    def _log(self, message: str) -> None:
        if not self._log_path:
            return
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a", encoding="utf-8") as handle:
                handle.write(f"[{stamp}] {message}\n")
        except OSError:
            pass

    def observe_adb_rows(
        self, rows: list[tuple[str, str]]
    ) -> tuple[list[str], list[str]]:
        """
        Update stable connection state from adb devices rows.

        Returns (newly_connected, newly_disconnected) serials (device state only).
        """
        self._poll_count += 1
        current_ready = {serial for serial, state in rows if state == "device"}
        all_serials = {serial for serial, _state in rows}

        newly_connected: list[str] = []
        newly_disconnected: list[str] = []

        for serial in current_ready:
            self._miss_counts[serial] = 0
            if serial not in self._connected:
                self._connected.add(serial)
                newly_connected.append(serial)
            self._known[serial] = {"serial": serial, "adb_state": "device", "connected": True}

        for serial in list(self._connected):
            if serial in current_ready:
                continue
            if serial not in all_serials:
                misses = self._miss_counts.get(serial, 0) + 1
                self._miss_counts[serial] = misses
                if misses >= self.DISCONNECT_MISS_THRESHOLD:
                    self._connected.discard(serial)
                    newly_disconnected.append(serial)
                    entry = self._known.setdefault(serial, {"serial": serial})
                    entry["connected"] = False
                    entry["adb_state"] = "absent"
            else:
                state = next((st for s, st in rows if s == serial), "")
                if state != "device":
                    self._connected.discard(serial)
                    if serial not in newly_disconnected:
                        newly_disconnected.append(serial)
                    entry = self._known.setdefault(serial, {"serial": serial})
                    entry["connected"] = False
                    entry["adb_state"] = state

        for serial, state in rows:
            if serial not in self._known:
                self._known[serial] = {
                    "serial": serial,
                    "adb_state": state,
                    "connected": state == "device",
                }
            else:
                self._known[serial]["adb_state"] = state
                if state == "device":
                    self._known[serial]["connected"] = True

        for serial in newly_connected:
            self._log(f"connected {serial}")
        for serial in newly_disconnected:
            self._log(f"disconnected {serial}")

        return newly_connected, newly_disconnected

    def should_refresh_label(self, serial: str) -> bool:
        if serial not in self._labels:
            return True
        return self._poll_count % self.LABEL_REFRESH_EVERY_POLLS == 0

    def set_label(self, serial: str, label: str) -> None:
        self._labels[serial] = label

    def get_label(self, serial: str, default: str) -> str:
        return self._labels.get(serial, default)

    def remember_serial(self, serial: str, label: str = "", connected: bool = False) -> None:
        if label:
            self._labels[serial] = label
        entry = self._known.setdefault(serial, {"serial": serial})
        entry["connected"] = connected
        if connected:
            self._connected.add(serial)
            self._miss_counts[serial] = 0

    def stable_ready_serials(self) -> set[str]:
        return set(self._connected)

    def known_entries(self) -> dict[str, dict]:
        return dict(self._known)


def connection_event_banner(
    newly_connected: list[str],
    newly_disconnected: list[str],
    label_for_serial,
) -> dict | None:
    """Build a banner dict for connect/disconnect edges, or None."""
    if newly_connected:
        serial = newly_connected[-1]
        label = label_for_serial(serial)
        return {
            "level": "OK",
            "message": f"Device connected: {label}",
            "ttl": 4,
        }
    if newly_disconnected:
        serial = newly_disconnected[-1]
        label = label_for_serial(serial)
        return {
            "level": "WARN",
            "message": f"Device disconnected: {label}",
            "ttl": 4,
        }
    return None
