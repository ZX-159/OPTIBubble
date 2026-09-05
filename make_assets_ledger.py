"""
Asset generator — OPTIBubble LEDGER brand assets (new design, 2026).

Ledger identity — "the grading desk": a calm, warm product look that keeps the
OMR / answer-sheet concept. Blue = the machine (one accent); pen-red is reserved
strictly for human-override moments. The sheet stays the hero.

Wordmark is set in the bundled OPTIBubbleDoubleBold font (converted to a web
font as optibubble/web/fonts/optibubble.woff2). The icon is a flat accent-blue
tile with four machine-vision corner brackets and a single marked bubble with a
grading tick — legible down to a 32 px favicon.

Outputs:
  assets/icon.png                     1024px source of truth (+ sizes + .ico)
  optibubble/web/assets/icon-128.png  the favicon the app actually serves
  src-tauri/icons/                    full Tauri icon set (incl. .ico)
  optibubble/web/assets/logo-wordmark-white.png
  optibubble/web/assets/logo-wordmark-navy.png

Run:  python make_assets_ledger.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "optibubble" / "fonts"
WEB_ASSETS = ROOT / "optibubble" / "web" / "assets"
DOCS = ROOT / "docs"

# LEDGER palette
ACCENT = (47, 111, 237)          # the machine
ACCENT_HI = (31, 91, 214)        # pressed / focus
INK = (27, 36, 48)               # text
PAPER = (251, 247, 238)          # the sheet
PAPER_EDGE = (239, 231, 214)     # sheet border / shadow
PEN = (229, 72, 77)              # grading pen — human override only
WHITE = (255, 255, 255)
INK_TXT = (235, 237, 240)        # light ink for dark chrome wordmark

OPTI = str(FONTS / "OPTIBubbleDoubleBold.otf")
OS_SEMI = str(FONTS / "OpenSans-SemiBold.ttf")
OS_REG = str(FONTS / "OpenSans-Regular.ttf")


def draw_tracked(draw, xy, s, font, fill, tracking=0.0):
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


def corner_brackets(d, x0, y0, x1, y1, length, width, color):
    """Four machine-vision L-marks."""
    for (cx, cy, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1),
                             (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line([(cx, cy), (cx + dx * length, cy)], fill=color, width=width)
        d.line([(cx, cy), (cx, cy + dy * length)], fill=color, width=width)


# ------------------------------------------------------------------- icon
def make_icon(out: Path, size: int = 1024) -> None:
    """Flat accent-blue tile · white corner brackets · one marked bubble + tick."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # rounded accent-blue tile
    d.rounded_rectangle([48, 48, size - 48, size - 48], radius=220, fill=ACCENT)

    m = int(size * 0.10)          # bracket margin
    bl = int(size * 0.16)         # bracket arm length
    bw = int(size * 0.055)        # bracket stroke width
    corner_brackets(d, m, m, size - m, size - m, length=bl, width=bw, color=WHITE)

    # a small "answer sheet" — three faint empty bubbles and one filled mark
    cx, cy = size * 0.5, size * 0.5
    r = size * 0.10
    ring = max(3, int(size * 0.012))
    # empty bubble (left)
    d.ellipse([cx - r * 2.3 - r, cy - 0.6 * r, cx - r * 2.3 + r, cy + 0.6 * r],
              outline=WHITE, width=ring)
    # empty bubble (right)
    d.ellipse([cx + r * 2.3 - r, cy - 0.6 * r, cx + r * 2.3 + r, cy + 0.6 * r],
              outline=WHITE, width=ring)
    # central MARKED bubble (filled dark)
    d.ellipse([cx - r * 1.5, cy - r * 1.5, cx + r * 1.5, cy + r * 1.5], fill=INK)
    # grading tick in pen-red on the marked bubble
    t = max(6, int(size * 0.028))
    d.line([(cx - r * 0.85, cy + r * 0.10), (cx - r * 0.15, cy + r * 0.75),
            (cx + r * 0.9, cy - r * 0.65)], fill=PEN, width=t, joint="curve")

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    for s2 in (512, 256, 128, 64, 32):
        img.resize((s2, s2), Image.LANCZOS).save(out.with_name(
            out.stem + f"-{s2}.png"))
    img.resize((256, 256), Image.LANCZOS).save(
        out.with_name("icon.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
               (256, 256)])
    print("✓", out)


# ---------------------------------------------------------------- wordmark
def make_wordmark(color, tagline_color, out: Path) -> None:
    f_main = ImageFont.truetype(OPTI, 200)
    f_tag = ImageFont.truetype(OS_SEMI, 40)
    s = "OPTIBubble"
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w_main = int(sum(dummy.textlength(c, font=f_main) for c in s)) + 40
    asc, desc = f_main.getmetrics()
    h_main = asc + desc
    pad = 60
    W = w_main + pad * 2
    H = h_main + pad * 2 + 84
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad, pad), s, font=f_main, fill=color)
    draw_tracked(d, (pad + 6, pad + h_main + 6), "SCAN. GRADE. DONE.",
                 f_tag, tagline_color, tracking=10)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print("✓", out)


if __name__ == "__main__":
    assets = ROOT / "assets"
    tauri_icons = ROOT / "src-tauri" / "icons"
    tauri_icons.mkdir(parents=True, exist_ok=True)

    # brand images served by the app (web/assets)
    make_wordmark(INK_TXT, ACCENT_HI, WEB_ASSETS / "logo-wordmark-white.png")
    make_wordmark(INK, (110, 116, 128), WEB_ASSETS / "logo-wordmark-navy.png")

    # icon source of truth + the favicon the app actually serves
    make_icon(assets / "icon.png")
    shutil.copy(assets / "icon-128.png", WEB_ASSETS / "icon-128.png")
    for stale in WEB_ASSETS.glob("icon-*.png"):
        if stale.name != "icon-128.png":
            stale.unlink()

    # native shell icon set (Windows / macOS / Linux bundles)
    shutil.copy(assets / "icon-32.png", tauri_icons / "32x32.png")
    shutil.copy(assets / "icon-128.png", tauri_icons / "128x128.png")
    shutil.copy(assets / "icon-256.png", tauri_icons / "128x128@2x.png")
    shutil.copy(assets / "icon-512.png", tauri_icons / "icon.png")
    shutil.copy(assets / "icon.ico", tauri_icons / "icon.ico")

    # tidy the intermediate sizes from assets/
    import os
    for stale in assets.glob("icon-*.png"):
        os.remove(stale)
    print("done")
