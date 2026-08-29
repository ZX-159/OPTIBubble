# -*- mode: python ; coding: utf-8 -*-
"""
Freeze the OPTIBubble engine into a single self-contained binary.

    pyinstaller optibubble.spec --distpath src-tauri/engine --noconfirm

The Tauri shell looks for `engine/optibubble-engine[.exe]` next to itself and
spawns it instead of `python main.py`, so end users need nothing installed.
Bundle size ≈ 60–95 MB (OpenCV dominates).
"""
from pathlib import Path

root = Path(SPECPATH)

# bundle the web UI and fonts exactly where optibumble expects them
datas = []
for sub in ("web", "fonts"):
    for p in (root / "optibubble" / sub).rglob("*"):
        if p.is_file():
            # keep the exact directory structure (web/fonts/…, web/assets/…)
            datas.append((str(p), str(p.parent.relative_to(root))))

a = Analysis(
    ["main.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "qrcode.image.pil",     # selected dynamically inside qrcode
        "pymupdf",              # imported lazily for previews
        
    ],
    excludes=["selftest", "playwright", "tkinter", "pytest",
              "IPython", "jedi", "matplotlib", "pandas", "scipy",
              "prompt_toolkit", "pydoc_data"],
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
    console=True,           # server process — keep stdout/stderr visible
)
