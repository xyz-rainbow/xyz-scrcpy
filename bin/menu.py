#!/usr/bin/env python3
import fcntl
import os
import re
import shutil
import signal
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path

from config_loader import load_config, save_config

BRAND_NAME = "RAINBOWTECHNOLOGY"
LOGO = [
    r"██╗  ██╗ ██╗   ██╗ ███████╗",
    r"╚██╗██╔╝ ╚██╗ ██╔╝ ╚══███╔╝",
    r" ╚███╔╝   ╚████╔╝    ███╔╝ ",
    r" ██╔██╗    ╚██╔╝    ███╔╝  ",
    r"██╔╝ ██╗    ██║    ███████╗",
    r"╚═╝  ╚═╝    ╚═╝    ╚══════╝",
]

RED, GREEN, MAGENTA, ORANGE, WHITE, RESET = (
    "\033[91m",
    "\033[38;5;118m",
    "\033[35m",
    "\033[38;5;208m",
    "\033[37m",
    "\033[0m",
)
NEON_PINK = "\033[38;5;213m"

ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")
ROOT_DIR = Path(__file__).resolve().parent.parent
LOCK_PATH = "/tmp/xyz_menu.lock"
INSTALLER_PATH = ROOT_DIR / "install_xyz.py"
LIME = "\033[38;5;154m"
MIC_BUS_NAME = "xyz-mic-input"
MIC_BUS_SINK = f"{MIC_BUS_NAME}-sink"


def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def visible_len(text):
    return len(ANSI_PATTERN.sub("", text))


def center_line(text, width):
    pad = max(0, (width - visible_len(text)) // 2)
    return (" " * pad) + text


def trunc_text(text, max_len):
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return "." * max_len
    return text[: max_len - 3] + "..."


def terminal_width():
    return max(40, min(120, shutil.get_terminal_size(fallback=(80, 24)).columns - 2))


def normalize_alias(alias):
    clean = re.sub(r"[^a-zA-Z0-9._-]", "-", str(alias).strip())
    clean = re.sub(r"-{2,}", "-", clean).strip("-")
    return clean or "xyz-scrcpy"


def prompt_text_input(prompt, default):
    sys.stdout.write("\n")
    sys.stdout.flush()
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else default


def sync_alias_launcher(alias):
    if not INSTALLER_PATH.exists():
        return False
    try:
        subprocess.run(
            [
                "python3",
                str(INSTALLER_PATH),
                "--action",
                "sync-alias",
                "--alias",
                alias,
                "--yes",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


def has_audio_pending(cfg):
    return any(
        [
            str(cfg.get("audio_target", "host")) != str(cfg.get("applied_audio_target", "host")),
            bool(cfg.get("active_recall", False)) != bool(cfg.get("applied_active_recall", False)),
            bool(cfg.get("microphone_bus", False)) != bool(cfg.get("applied_microphone_bus", False)),
        ]
    )


def normalize_audio_preferences(cfg):
    normalized = dict(cfg)
    if bool(normalized.get("active_recall", False)) and str(normalized.get("audio_target", "host")).lower() == "device":
        # Active Recall uses Android microphone capture, which requires host-side audio enabled.
        normalized["audio_target"] = "host"
    return normalized


def list_devices():
    try:
        raw = subprocess.check_output(["adb", "devices"], text=True).splitlines()
        serials = [line.split()[0] for line in raw if line.strip().endswith("device") and not line.startswith("List")]
        devices = []
        for serial in serials:
            model = subprocess.check_output(
                ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
                text=True,
            ).strip()
            devices.append({"serial": serial, "label": f"{model} ({serial})"})
        return devices
    except subprocess.SubprocessError:
        return []


def scrcpy_supports_microphone():
    try:
        output = subprocess.check_output(["scrcpy", "--help"], text=True, stderr=subprocess.STDOUT)
    except (subprocess.SubprocessError, OSError):
        return False
    lowered = output.lower()
    return "--audio-source" in lowered and "mic" in lowered


def ensure_microphone_bus(enabled):
    if not enabled:
        return False
    if sys.platform.startswith("win"):
        print("[WARN] Windows microphone bus requires a virtual audio cable (for example VB-CABLE).")
        print(f"[WARN] Configure that virtual input/output as '{MIC_BUS_NAME}' manually.")
        return False
    if sys.platform != "linux":
        print("[WARN] Microphone bus is currently implemented on Linux only.")
        return False
    if shutil.which("pactl") is None:
        print("[WARN] microphone_bus requires 'pactl' (PulseAudio/PipeWire).")
        return False
    try:
        existing_sources = subprocess.check_output(["pactl", "list", "short", "sources"], text=True)
        if MIC_BUS_NAME in existing_sources:
            return True
        subprocess.run(
            ["pactl", "load-module", "module-null-sink", f"sink_name={MIC_BUS_SINK}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "pactl",
                "load-module",
                "module-remap-source",
                f"master={MIC_BUS_SINK}.monitor",
                f"source_name={MIC_BUS_NAME}",
                f"source_properties=device.description={MIC_BUS_NAME}",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.SubprocessError, OSError):
        print("[WARN] Unable to initialize microphone bus.")
        return False


def launch_scrcpy(serial, cfg):
    cfg = normalize_audio_preferences(cfg)
    audio_target = str(cfg.get("audio_target", "host")).lower()
    active_recall = bool(cfg.get("active_recall", False))
    microphone_bus = bool(cfg.get("microphone_bus", False))
    cmd = ["scrcpy", "-s", serial, "--render-driver=software"]
    if audio_target == "device":
        cmd.append("--no-audio")
    if active_recall:
        if scrcpy_supports_microphone():
            cmd.append("--audio-source=mic")
        else:
            print("[WARN] Microphone is not supported by current scrcpy version.")
    launch_env = dict(os.environ)
    if microphone_bus and ensure_microphone_bus(microphone_bus):
        # Route Android microphone/audio stream into the dedicated virtual sink.
        launch_env["PULSE_SINK"] = MIC_BUS_SINK
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=launch_env)


def render_menu(opts, idx, width):
    border = "=" * width
    out = [
        center_line("[SPACE] [ENTER] [ESC]".center(width), width),
        center_line(f"{RED}{border}{RESET}", width),
        "",
    ]
    for line in LOGO:
        out.append(center_line(f"{GREEN}{line.center(width)}{RESET}", width))
    out.append("")
    for i, opt in enumerate(opts):
        label = trunc_text(opt, width - 4)
        if i == idx:
            line = f"> {ORANGE}{label}{RESET} <"
        else:
            line = label
        out.append(center_line(line, width))
    out.extend(
        [
            "",
            center_line(f"{GREEN}{border}{RESET}", width),
            center_line(f"{NEON_PINK}[{BRAND_NAME}]".center(width) + f"{RESET}", width),
            center_line(f"{GREEN}{border}{RESET}", width),
        ]
    )
    return out


def settings_screen(cfg):
    temp_cfg = dict(cfg)
    temp_cfg["command_alias"] = normalize_alias(temp_cfg.get("command_alias", "xyz-scrcpy"))
    field_idx = 0
    fields = [
        "command_alias",
        "audio_target",
        "active_recall",
        "microphone_bus",
        "auto_start",
        "auto_discover",
        "pause_on_exit",
        "exit_pause_minutes",
        "APPLY",
        "CANCEL",
    ]
    while True:
        width = terminal_width()
        border = "=" * width
        pause_toggle_label = "Start" if temp_cfg["pause_on_exit"] else "Pause"
        lines = [
            center_line(f"{GREEN}{border}{RESET}", width),
            center_line(f"{MAGENTA}SETTINGS{RESET}", width),
            center_line(f"{GREEN}{border}{RESET}", width),
            "",
        ]
        rows = [
            f"Command alias: {temp_cfg['command_alias']}",
            f"Audio target: {temp_cfg.get('audio_target', 'host').upper()}",
            f"Active Recall: {'ON' if temp_cfg.get('active_recall', False) else 'OFF'}",
            f"Microphone Bus ({MIC_BUS_NAME}): {'ON' if temp_cfg.get('microphone_bus', False) else 'OFF'}",
            f"Auto-start: {'ON' if temp_cfg['auto_start'] else 'OFF'}",
            f"[Auto-Discover] [{'ON' if temp_cfg.get('auto_discover', True) else 'OFF'}]",
            f"[{pause_toggle_label}] on EXIT",
            f"Pause duration (minutes): {temp_cfg['exit_pause_minutes']}",
            "[Apply]",
            "[Cancel]",
        ]
        for i, row in enumerate(rows):
            name = fields[i]
            text = trunc_text(row, width - 4)
            changed = name in temp_cfg and temp_cfg.get(name) != cfg.get(name)
            if changed:
                text = f"{RED}{text}{RESET}"
            lines.append(center_line((f"> {text}" if i == field_idx else f"  {text}"), width))
        lines.append("")
        lines.append(center_line("[LEFT/RIGHT] edit [ENTER] select/apply [ESC] back", width))
        os.system("clear")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

        key = get_key()
        if key == "\x1b[A":
            field_idx = (field_idx - 1) % len(fields)
        elif key == "\x1b[B":
            field_idx = (field_idx + 1) % len(fields)
        elif key in ("\x1b[C", "\x1b[D", " "):
            name = fields[field_idx]
            if name == "audio_target":
                current = str(temp_cfg.get("audio_target", "host")).lower()
                temp_cfg["audio_target"] = "device" if current == "host" else "host"
            elif name == "active_recall":
                temp_cfg["active_recall"] = not bool(temp_cfg.get("active_recall", False))
            elif name == "microphone_bus":
                temp_cfg["microphone_bus"] = not bool(temp_cfg.get("microphone_bus", False))
            elif name == "auto_start":
                temp_cfg["auto_start"] = not temp_cfg["auto_start"]
            elif name == "auto_discover":
                temp_cfg["auto_discover"] = not bool(temp_cfg.get("auto_discover", True))
            elif name == "pause_on_exit":
                temp_cfg["pause_on_exit"] = not temp_cfg["pause_on_exit"]
            elif name == "exit_pause_minutes":
                step = 10 if key == "\x1b[C" else -10
                temp_cfg["exit_pause_minutes"] = max(1, int(temp_cfg["exit_pause_minutes"]) + step)
        elif key == "\r":
            name = fields[field_idx]
            if name == "audio_target":
                current = str(temp_cfg.get("audio_target", "host")).lower()
                temp_cfg["audio_target"] = "device" if current == "host" else "host"
            elif name == "active_recall":
                temp_cfg["active_recall"] = not bool(temp_cfg.get("active_recall", False))
            elif name == "microphone_bus":
                temp_cfg["microphone_bus"] = not bool(temp_cfg.get("microphone_bus", False))
            elif name == "command_alias":
                os.system("clear")
                try:
                    entered = prompt_text_input("Enter new command alias", temp_cfg["command_alias"])
                except EOFError:
                    entered = temp_cfg["command_alias"]
                temp_cfg["command_alias"] = normalize_alias(entered)
            elif name == "auto_start":
                temp_cfg["auto_start"] = not temp_cfg["auto_start"]
            elif name == "auto_discover":
                temp_cfg["auto_discover"] = not bool(temp_cfg.get("auto_discover", True))
            elif name == "pause_on_exit":
                temp_cfg["pause_on_exit"] = not temp_cfg["pause_on_exit"]
            elif name == "APPLY":
                temp_cfg["command_alias"] = normalize_alias(temp_cfg["command_alias"])
                temp_cfg = normalize_audio_preferences(temp_cfg)
                save_config(temp_cfg)
                sync_alias_launcher(temp_cfg["command_alias"])
                return load_config(), "apply"
            elif name == "CANCEL":
                return cfg, "cancel"
        elif key == "\x1b":
            return cfg, "cancel"


def activate_pause_on_exit(cfg):
    cfg["pause_active"] = True
    cfg["pause_wait_reconnect"] = True
    cfg["pause_seen_disconnect"] = False
    pause_minutes = int(cfg.get("exit_pause_minutes", 1440))
    cfg["pause_until_epoch"] = int(time.time()) + (max(1, pause_minutes) * 60)
    save_config(cfg)


def main():
    signal.signal(signal.SIGWINCH, lambda *_: None)
    lock_file = open(LOCK_PATH, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)

    idx = 0
    cfg = load_config()
    try:
        while True:
            width = terminal_width()
            devices = list_devices()
            device_labels = [d["label"] for d in devices]
            restart_label = "RESTART"
            if has_audio_pending(cfg):
                restart_label = f"{LIME}RESTART{RESET}"
            else:
                restart_label = f"{RED}RESTART{RESET}"
            opts = device_labels + ["SETTINGS", restart_label, "EXIT"]
            if idx >= len(opts):
                idx = 0

            os.system("clear")
            sys.stdout.write("\n".join(render_menu(opts, idx, width)))
            sys.stdout.flush()

            key = get_key()
            if key == "\x1b[A":
                idx = (idx - 1) % len(opts)
            elif key == "\x1b[B":
                idx = (idx + 1) % len(opts)
            elif key == "\r":
                selected = opts[idx]
                if selected == "EXIT":
                    if cfg.get("pause_on_exit"):
                        activate_pause_on_exit(cfg)
                    break
                if selected == "SETTINGS":
                    cfg, _ = settings_screen(cfg)
                    continue
                if "RESTART" in selected:
                    target_serial = cfg.get("last_device_serial")
                    if not target_serial and devices:
                        target_serial = devices[0]["serial"]
                    if target_serial:
                        cfg = normalize_audio_preferences(cfg)
                        subprocess.run(
                            ["pkill", "-f", f"scrcpy.*-s[[:space:]]*{target_serial}"],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        time.sleep(0.4)
                        launch_scrcpy(target_serial, cfg)
                        cfg["applied_audio_target"] = cfg.get("audio_target", "host")
                        cfg["applied_active_recall"] = bool(cfg.get("active_recall", False))
                        cfg["applied_microphone_bus"] = bool(cfg.get("microphone_bus", False))
                        cfg["last_device_serial"] = target_serial
                        save_config(cfg)
                        cfg = load_config()
                    continue
                match = re.search(r"\((.*?)\)$", selected)
                device_serial = match.group(1) if match else selected
                cfg = normalize_audio_preferences(cfg)
                launch_scrcpy(device_serial, cfg)
                cfg["applied_audio_target"] = cfg.get("audio_target", "host")
                cfg["applied_active_recall"] = bool(cfg.get("active_recall", False))
                cfg["applied_microphone_bus"] = bool(cfg.get("microphone_bus", False))
                cfg["last_device_serial"] = device_serial
                save_config(cfg)
                cfg = load_config()
            elif key == "\x1b":
                break
    finally:
        if os.path.exists(LOCK_PATH):
            os.remove(LOCK_PATH)
        os.system("clear")


if __name__ == "__main__":
    main()
