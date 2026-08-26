"""
Asset generator — renders the OPTIBubble brand assets with PIL.

REGMARK design language — paper · ink · grading pen:
flat surfaces, no gradients/glows, graph-paper grids and registration
brackets. Wordmark set in OPTIBubbleDoubleBold; taglines in Open Sans.

Outputs (exactly the set the app uses):
  optibubble/web/assets/  logo-wordmark-white.png · logo-wordmark-navy.png · icon-128.png
  src-tauri/icons/       full Tauri icon set incl. icon.ico
  assets/icon.png        1024px source of truth (+ icon.ico)
  docs/hero.png          README banner

Run:  python make_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "optibubble" / "fonts"
WEB_ASSETS = ROOT / "optibubble" / "web" / "assets"
DOCS = ROOT / "docs"

# REGMARK palette — paper · ink · grading pen
CARBON = (12, 13, 17)          # bg0
CARBON_2 = (26, 28, 35)        # lifted surface (bg2)
INK_TXT = (234, 235, 239)      # light ink
PAPER_INK = (25, 26, 31)       # dark ink (paper theme wordmark)
PERSIMMON = (255, 90, 45)      # brand — the grading pen
GREY = (104, 108, 121)         # faint annotation

OPTI = str(FONTS / "OPTIBubbleDoubleBold.otf")
OS_SEMI = str(FONTS / "OpenSans-SemiBold.ttf")
OS_REG = str(FONTS / "OpenSans-Regular.ttf")


def draw_tracked(draw, xy, s, font, fill, tracking=0.0):
    """Draw text with letter-spacing; returns final x."""
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


def brackets(d, x0, y0, x1, y1, length, width, color):
    """Draw the REGMARK registration brackets (corner L-marks)."""
    for (cx, cy, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1),
                             (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line([(cx, cy), (cx + dx * length, cy)], fill=color, width=width)
        d.line([(cx, cy), (cx, cy + dy * length)], fill=color, width=width)


# ---------------------------------------------------------------- wordmark
def make_wordmark(color, tagline_color, out: Path) -> None:
    f_main = ImageFont.truetype(OPTI, 210)
    f_tag = ImageFont.truetype(OS_SEMI, 40)
    s = "OPTIBubble"
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w_main = int(sum(dummy.textlength(c, font=f_main) for c in s)) + 40
    asc, desc = f_main.getmetrics()
    h_main = asc + desc
    pad = 60
    W = w_main + pad * 2
    H = h_main + pad * 2 + 86
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad, pad), s, font=f_main, fill=color)
    draw_tracked(d, (pad + 6, pad + h_main + 6), "SCAN. GRADE. DONE.",
                 f_tag, tagline_color, tracking=10)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print("✓", out)


# ------------------------------------------------------------------- icon
def make_icon(out: Path, size: int = 1024) -> None:
    """Flat graphite tile · white bubble outlines · one persimmon-filled mark."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 40, size - 40, size - 40], radius=96, fill=CARBON)

    rows, cols = 3, 4
    r = 54
    gx, gy = 196, 336
    pitch_x, pitch_y = 176, 198
    for ri in range(rows):
        for ci in range(cols):
            cx, cy = gx + ci * pitch_x + ri * 22, gy + ri * pitch_y
            filled = (ri, ci) == (1, 2)
            if filled:
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PERSIMMON)
            else:
                d.ellipse([cx - r, cy - r, cx + r, cy + r],
                          outline=(234, 235, 239, 220), width=13)
    # grading check
    d.line([(700, 690), (760, 750), (884, 596)], fill=INK_TXT, width=34, joint="curve")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    for s2 in (512, 256, 128, 64, 32):
        img.resize((s2, s2), Image.LANCZOS).save(out.with_name(
            out.stem + f"-{s2}.png"))
    img.resize((256, 256), Image.LANCZOS).save(
        out.with_name("icon.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("✓", out)


# ------------------------------------------------------------------- hero
def make_hero(out: Path, W: int = 1720, H: int = 640) -> None:
    """Flat carbon banner · graph-paper grid · registration brackets."""
    img = Image.new("RGB", (W, H), CARBON)
    d = ImageDraw.Draw(img)

    # graph-paper grid (subtle)
    grid = (36, 38, 46)
    for x in range(0, W, 26):
        d.line([(x, 0), (x, H)], fill=grid)
    for y in range(0, H, 26):
        d.line([(0, y), (W, y)], fill=grid)

    brackets(d, 40, 40, W - 40, H - 40, length=26, width=2, color=(120, 124, 136))

    f_main = ImageFont.truetype(OPTI, 164)
    f_tag = ImageFont.truetype(OS_SEMI, 30)
    f_small = ImageFont.truetype(OS_REG, 24)
    f_micro = ImageFont.truetype(OS_SEMI, 18)

    # left: wordmark + tagline
    x0, y0 = 120, 168
    d.text((x0, y0), "OPTIBubble", font=f_main, fill=INK_TXT)
    asc, desc = f_main.getmetrics()
    ty = y0 + asc + desc + 2
    d.line([(x0 + 2, ty + 10), (x0 + 560, ty + 10)], fill=PERSIMMON, width=3)
    draw_tracked(d, (x0 + 2, ty + 22), "LOCAL OMR GRADING · MOBILE BRIDGE",
                 f_tag, PERSIMMON, tracking=7)

    d.text((x0, y0 + 330), "Print answer sheets → scan with any phone → grade with OpenCV.",
           font=f_small, fill=(150, 154, 166))
    d.text((x0, y0 + 372), "100% local. No cloud. No subscriptions. Export to CSV.",
           font=f_small, fill=(150, 154, 166))
    d.text((x0, H - 78), "CARBON · PERSIMMON · OPEN SANS", font=f_micro, fill=GREY)

    # right: stylised sheet on a lifted surface
    sx, sy, sw, sh = W - 470, 96, 330, 448
    sh_img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh_img)
    sd.rounded_rectangle([0, 0, sw - 1, sh - 1], 6, fill=CARBON_2)
    brackets(sd, 18, 18, sw - 18, sh - 18, length=16, width=3, color=INK_TXT)
    # QR-ish block (persimmon)
    for rxi in range(6):
        for ryi in range(6):
            if (rxi * 7 + ryi * 13) % 3 == 0:
                sd.rectangle([sw - 108 + rxi * 12, 26 + ryi * 12,
                              sw - 108 + rxi * 12 + 9, 26 + ryi * 12 + 9],
                             fill=PERSIMMON)
    # bubble rows
    for ri in range(11):
        yq = 96 + ri * 30
        sd.text((22, yq - 9), f"{ri + 1:>2}", font=ImageFont.truetype(OS_SEMI, 16),
                fill=(120, 124, 136))
        for ci in range(4):
            cx = 68 + ci * 34
            if (ri, ci) in ((2, 1), (4, 3), (7, 0), (9, 2)):
                sd.ellipse([cx - 10, yq - 10, cx + 10, yq + 10], fill=PERSIMMON)
            else:
                sd.ellipse([cx - 10, yq - 10, cx + 10, yq + 10],
                           outline=(160, 164, 176), width=3)
    img.paste(sh_img, (sx, sy), sh_img)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=95)
    print("✓", out)


if __name__ == "__main__":
    import shutil

    assets = ROOT / "assets"
    tauri_icons = ROOT / "src-tauri" / "icons"
    tauri_icons.mkdir(parents=True, exist_ok=True)

    # brand images served by the app (web/assets)
    make_wordmark(INK_TXT, PERSIMMON, WEB_ASSETS / "logo-wordmark-white.png")
    make_wordmark(PAPER_INK, (120, 122, 132), WEB_ASSETS / "logo-wordmark-navy.png")

    # icon source of truth + the one favicon size the app actually serves
    make_icon(assets / "icon.png")
    shutil.copy(assets / "icon-128.png", WEB_ASSETS / "icon-128.png")
    for stale in WEB_ASSETS.glob("icon-*.png"):
        if stale.name != "icon-128.png":
            stale.unlink()

    # native shell icon set (Windows/macOS/Linux bundles)
    shutil.copy(assets / "icon-32.png", tauri_icons / "32x32.png")
    shutil.copy(assets / "icon-128.png", tauri_icons / "128x128.png")
    shutil.copy(assets / "icon-256.png", tauri_icons / "128x128@2x.png")
    shutil.copy(assets / "icon-512.png", tauri_icons / "icon.png")
    shutil.copy(assets / "icon.ico", tauri_icons / "icon.ico")

    # README hero (docs only)
    make_hero(DOCS / "hero.png")

    # tidy the intermediate sizes from assets/
    for stale in assets.glob("icon-*.png"):
        stale.unlink()
    print("done")
