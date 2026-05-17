#!/usr/bin/env bash
# XYZ-scrcpy Unix dev installer - interactive bash menu (not full-screen TUI).
# Intended for Linux and macOS clones. Uses uv, .venv, then install_xyz.py (no --yes).
# [4] Diagnose: install_xyz diagnose is Windows-only; this menu shows a short notice.
# ANSI: enabled on TTY when tput reports >= 8 colors. Confirmations: [Y/n], Enter = yes.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT" || exit 1

PYTHON_VENV="${REPO_ROOT}/.venv/bin/python3"
TW=78
USE_COLOR=0
C_GREEN=$'\033[38;5;118m'
C_MAG=$'\033[35m'
C_PINK=$'\033[38;5;213m'
C_RST=$'\033[0m'

confirm_yes_no() {
  local msg="$1"
  printf '%s\n' "$msg"
  local xyzc=""
  # shellcheck disable=SC2162
  read -r -p "Confirm [Y/n]: " xyzc || true
  local lc
  lc=$(printf '%s' "${xyzc}" | tr '[:upper:]' '[:lower:]')
  case "${lc}" in
    "" | y | yes) CONFIRM=1 ;;
    n | no) CONFIRM=0 ;;
    *) CONFIRM=1 ;;
  esac
}

init_color() {
  USE_COLOR=0
  if [[ ! -t 1 ]]; then
    return
  fi
  local n
  n="$(tput colors 2>/dev/null)" || n="0"
  if [[ "${n}" =~ ^[0-9]+$ ]] && ((n >= 8)); then
    USE_COLOR=1
  fi
}

get_term_width() {
  local w="${COLUMNS:-}"
  if [[ -z "${w}" ]] || [[ ! "${w}" =~ ^[0-9]+$ ]]; then
    w="$(tput cols 2>/dev/null)" || w="80"
  fi
  [[ "${w}" =~ ^[0-9]+$ ]] || w="80"
  w=$((w - 3))
  if ((w < 40)); then w=40; fi
  if ((w > 120)); then w=120; fi
  TW=$w
}

draw_menu_frame() {
  get_term_width
  local i w=""
  for ((i = 0; i < TW; i++)); do
    w+="="
  done
  if ((USE_COLOR == 1)); then
    printf '%b%s%b\n' "${C_GREEN}" "${w}" "${C_RST}"
    printf '%b  XYZ-SCRCPY - Unix dev installer%b\n' "${C_MAG}" "${C_RST}"
    printf '%b%s%b\n' "${C_GREEN}" "${w}" "${C_RST}"
    printf '%b  RAINBOWTECHNOLOGY%b\n' "${C_PINK}" "${C_RST}"
    printf '%b%s%b\n' "${C_GREEN}" "${w}" "${C_RST}"
  else
    printf '%s\n' "${w}"
    printf '  XYZ-SCRCPY - Unix dev installer\n'
    printf '%s\n' "${w}"
    printf '  RAINBOWTECHNOLOGY\n'
    printf '%s\n' "${w}"
  fi
}

# 0 = uv ok, 1 = error, 2 = user declined install
ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  echo
  echo "uv was not found on PATH. It is required to manage the local .venv."
  echo "This will download and run the official Astral installer script (network)."
  confirm_yes_no "Install uv now via https://astral.sh/uv/install.sh"
  if [[ "${CONFIRM}" == "0" ]]; then
    return 2
  fi
  echo
  echo "Installing uv..."
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
    echo "curl/install.sh returned an error."
    return 1
  fi
  export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv is still not on PATH after install. Open a new shell and run ./installer.sh again."
    return 1
  fi
  return 0
}

do_bootstrap() {
  if [[ ! -d "${REPO_ROOT}/.venv" ]]; then
    echo "[bootstrap] Creating virtual environment..."
    if ! uv venv .venv; then
      return 1
    fi
  fi
  echo "[bootstrap] Installing Python dependencies..."
  if ! uv pip install -r .requirements.txt; then
    return 1
  fi
  echo "[bootstrap] Installing adb/scrcpy into vendor/ (network)..."
  if ! "${PYTHON_VENV}" setup_vendor.py; then
    echo "[WARN] vendor tools incomplete; install may continue with system adb/scrcpy."
  fi
  echo "[bootstrap] Done."
  return 0
}

run_install_xyz() {
  local action="$1"
  local pyret=0
  "${PYTHON_VENV}" install_xyz.py --action "${action}" || pyret=$?
  if ((pyret != 0)); then
    echo
    echo "install_xyz.py exited with code ${pyret}."
    read -r -p "Press Enter to continue..." _ || true
  fi
  if [[ "${action}" == "install" ]] && ((pyret == 0)); then
    echo
    echo "Tip: open a NEW shell or run hash -r so your PATH picks up the launcher."
  fi
}

read_menu_choice() {
  local c
  while true; do
    read -r -n 1 -p "Select [1-5 or Q]: " c || {
      echo
      exit 0
    }
    echo
    case "${c}" in
      1 | 2 | 3 | 4 | 5 | q | Q)
        MENU_CHOICE=${c}
        break
        ;;
      *)
        echo "Invalid choice."
        ;;
    esac
  done
}

opt_refresh() {
  confirm_yes_no "Update or create .venv, pip deps, and vendor adb/scrcpy (uses network)"
  if [[ "${CONFIRM}" == "0" ]]; then
    return
  fi
  if [[ ! -f "${PYTHON_VENV}" ]]; then
    confirm_yes_no "Create new .venv in this repo now"
    if [[ "${CONFIRM}" == "0" ]]; then
      return
    fi
  fi
  if ! do_bootstrap; then
    echo "Update failed."
    read -r -p "Press Enter to continue..." _ || true
  fi
}

opt_install() {
  if [[ ! -f "${PYTHON_VENV}" ]]; then
    echo "No .venv Python found. Choose [1] first to create the dev environment."
    read -r -p "Press Enter to continue..." _ || true
    return
  fi
  confirm_yes_no "Run INSTALL via install_xyz.py (you will be asked again inside Python)"
  if [[ "${CONFIRM}" == "0" ]]; then
    return
  fi
  run_install_xyz install
}

opt_uninstall() {
  if [[ ! -f "${PYTHON_VENV}" ]]; then
    echo "No .venv Python found. Choose [1] first to create the dev environment."
    read -r -p "Press Enter to continue..." _ || true
    return
  fi
  confirm_yes_no "Run UNINSTALL via install_xyz.py (you will be asked again inside Python)"
  if [[ "${CONFIRM}" == "0" ]]; then
    return
  fi
  run_install_xyz uninstall
}

opt_diagnose() {
  echo "Diagnose (install_xyz.py --action diagnose) is Windows-only today."
  echo "On Linux/macOS check: which adb, systemctl --user status, PATH, install log under the app dir."
  read -r -p "Press Enter to continue..." _ || true
}

opt_syncalias() {
  if [[ ! -f "${PYTHON_VENV}" ]]; then
    echo "No .venv Python found. Choose [1] first to create the dev environment."
    read -r -p "Press Enter to continue..." _ || true
    return
  fi
  confirm_yes_no "Run SYNC-ALIAS via install_xyz.py (you will be asked again inside Python)"
  if [[ "${CONFIRM}" == "0" ]]; then
    return
  fi
  run_install_xyz sync-alias
}

# --- entry ---
ensure_uv
UVRET=$?
if ((UVRET == 2)); then
  echo
  echo "You declined to install uv. Install manually from https://github.com/astral-sh/uv"
  read -r -p "Press Enter to exit..." _ || true
  exit 0
fi
if ((UVRET != 0)); then
  echo
  echo "uv is still not available after the install attempt."
  exit 1
fi

if [[ ! -f "${PYTHON_VENV}" ]]; then
  confirm_yes_no "Create .venv and install dependencies (may take a few minutes)"
  if [[ "${CONFIRM}" == "0" ]]; then
    echo "Skipping environment setup. Use menu option [1] later to create or refresh .venv."
  else
    if ! do_bootstrap; then
      echo "Bootstrap failed."
      exit 1
    fi
  fi
fi

init_color

while true; do
  draw_menu_frame
  echo
  echo "  [1] Update / create dev environment  (.venv, deps, vendor)"
  echo "  [2] Install (launcher PATH / service - interactive Python prompts)"
  echo "  [3] Uninstall (interactive Python prompts)"
  echo "  [4] Diagnose (Windows-only in install_xyz.py - see notice)"
  echo "  [5] Sync launcher alias only (install_xyz.py)"
  echo "  [Q] Quit"
  echo
  read_menu_choice
  case "${MENU_CHOICE}" in
    q | Q)
      exit 0
      ;;
    1) opt_refresh ;;
    2) opt_install ;;
    3) opt_uninstall ;;
    4) opt_diagnose ;;
    5) opt_syncalias ;;
  esac
done
