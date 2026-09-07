#!/bin/sh
# OPTIBubble Flatpak launcher.
#
# Runs the ENGINE FROM SOURCE (python3 main.py) — deliberately NOT a frozen
# PyInstaller binary. See packaging/flatpak/README.md for why:
#   * OSTree sandboxes keep /app immutable. PyInstaller's `--onefile` extracts
#     its bundle to /tmp (_MEIPASS) at launch, which is fragile in a sandbox.
#     Running from source writes nothing into /app at runtime.
#   * User data lives in the sandbox's persistent $XDG_DATA_HOME
#     (~/.var/app/com.optibubble.app/data/…), which the manifest grants access
#     to via --filesystem=xdg-data.
#
# The wrapper still honours the XDG data-dir chain and exposes the /app-installed
# Python packages on PYTHONPATH (installed by the python3-deps module).
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/OPTIBubbleData"
export PYTHONPATH="/app/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}"

exec python3 /app/optibubble-app/main.py --data-dir "$DATA_DIR" "$@"
