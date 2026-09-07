# -*- mode: python ; coding: utf-8 -*-
"""
Freeze the OPTIBubble engine into a single self-contained binary.
Used by CI (and for local test builds) BEFORE the Tauri shell bundles it:

    pyinstaller optibubble.spec --distpath src-tauri/engine --noconfirm

The Tauri shell looks for `engine/optibubble-engine[.exe]` next to itself and
spawns it instead of `python main.py`, so end users need nothing installed.

Asset layout
------------
`optibubble/config.py` resolves paths dynamically:
  * source run (`python main.py`)      → `<repo>/optibubble/{fonts,web}`
  * frozen executable                  → `sys._MEIPASS/optibubble/{fonts,web}`

The `datas` entries below place the assets exactly at `optibubble/fonts` and
`optibubble/web` inside the bundle, matching `BASE_DIR = app_root()/optibubble`.
The React SPA build (`optibubble/web/dist`) is included automatically because we
glob the whole `web` tree — CI builds it before this freeze runs.
"""

from pathlib import Path

from PyInstaller.utils.hooks import (collect_data_files, collect_dynamic_libs,
                                     collect_submodules)

root = Path(SPECPATH)


def _collect(src_dir: Path) -> list:
    """All files under ``src_dir``, each mapped to its own *relative* destination
    so the sub-directory structure (``web/fonts/``, ``web/dist/``, ``web/assets/``)
    is preserved inside the bundle. Returns ``(source_file, dest_dir)`` pairs.

    ``dest_dir`` is computed from the project ``root`` so files land at
    ``optibubble/fonts/...`` and ``optibubble/web/...`` exactly where
    ``config.app_root()`` looks for them at runtime.
    """
    out = []
    for p in src_dir.rglob("*"):
        if p.is_file():
            out.append((str(p), str(p.parent.relative_to(root))))
    return out


# Static assets explicitly packaged into the bundle. These are the only material
# the engine needs that is not imported as Python — fonts for the ReportLab sheet
# generator and the whole web UI (app.html/scan.html, dist, assets, web fonts).
# Using the per-file relative destination keeps the nested structure intact.
datas = []
datas += _collect(root / "optibubble" / "fonts")
datas += _collect(root / "optibubble" / "web")

# PyInstaller + numpy 2.x: the `numpy._core` package is compiled C-extension +
# Python and must be collected wholesale, or the frozen binary fails with
# `ModuleNotFoundError: No module named 'numpy._core._exceptions'` on launch.
# Collecting submodules + the shared libs makes the freeze run on any numpy 2.x.
datas += collect_dynamic_libs("numpy")
datas += collect_data_files("numpy")

hidden = [
    "qrcode.image.pil",        # selected dynamically inside qrcode
    "pymupdf",                 # imported lazily for previews / selftest
    "PIL._tkinter_finder",     # Pillow's optional Tk interop registry
]
hidden += collect_submodules("numpy")

a = Analysis(
    ["main.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    excludes=[
        "selftest", "playwright", "tkinter", "pytest",
        "IPython", "jedi", "matplotlib", "pandas", "scipy",
        "prompt_toolkit", "pydoc_data",
    ],
    noarchive=False,
)


pyz = PYZ(a.pure)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="optibubble-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,                 # server process — keep stdout/stderr visible
)

# A onefile binary. `sys._MEIPASS` points at the temp dir the engine unpacks to,
# so `app_root()` finds `optibubble/fonts` and `optibubble/web` at runtime.
