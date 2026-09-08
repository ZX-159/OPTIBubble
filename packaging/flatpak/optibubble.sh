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
# Robustness:
#   * Strip any PYTHONHOME/PYTHONPATH the environment may have injected (e.g. by
#     a packer). If one leaks in, python3 init against a foreign prefix and dies
#     with "Failed to import encodings". We set an explicit, known-good PYTHONPATH
#     to the app-installed packages instead.
#   * The packages are installed with pip --target into the version-agnostic
#     /app/optibubble/lib (see com.optibubble.app.yml), so PYTHONPATH is stable.
#   * WebKitGTK can abort with EGL_BAD_PARAMETER in a sandbox; force the
#     software / non-dmabuf compositing path so the webview renders.
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/OPTIBubbleData"
unset PYTHONHOME PYTHONEXECUTABLE PYTHONPLATLIBDIR PYTHONSAFEPATH 2>/dev/null || true
export PYTHONPATH="/app/optibubble/lib"
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1

exec python3 /app/optibubble-app/main.py --data-dir "$DATA_DIR" "$@"
