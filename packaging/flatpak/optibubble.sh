#!/bin/sh
# OPTIBubble Flatpak launcher — starts the engine and opens the UI.
# Data lives inside the sandbox's persistent home (~/.var/app/com.optibubble.app/…).
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/OPTIBubbleData"
exec python3 /app/optibubble-app/main.py --data-dir "$DATA_DIR" "$@"
