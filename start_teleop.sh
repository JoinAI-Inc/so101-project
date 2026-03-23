#!/usr/bin/env sh
set -eu

VENV_PY="/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python"
SCRIPT="/mnt/e/SO101_Project/scripts/teleop/teleop_so101_keyboard.py"

if [ ! -x "$VENV_PY" ]; then
  echo "[ERR] venv python not found: $VENV_PY" >&2
  exit 1
fi

if [ ! -e /dev/ttyACM0 ]; then
  echo "[WARN] /dev/ttyACM0 not found. Check SO101 USB passthrough to WSL." >&2
fi

exec "$VENV_PY" "$SCRIPT"
