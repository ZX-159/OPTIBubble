"""
Printable answer-sheet PDF generator (ReportLab).

Draws the sheet using the exact geometry from :mod:`optibubble.layout`, so the
OpenCV engine can find every bubble at a known position after perspective
correction.  The sheet includes:

* four solid 10 mm alignment squares (one in each corner),
* a QR code identifying the test session,
* the OPTIBubble wordmark (OPTIBubbleDoubleBold) in brand blue #2e5a99,
* an editable header: title, subject, custom instructions, text size and
  logo side — auto-fitted so it can never collide with the answer area,
* binary page-code dots (future multi-page support),
* a student-ID grid (up to 10 digits × values 0-9),
* up to 102 questions with A-E option bubbles.

Every generated layout passes :func:`optibubble.layout.validate_layout`
before a single PDF is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import qrcode
from PIL import Image
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

from .config import FONTS_DIR, FONT_OPEN_SANS, FONT_OPTI, LETTERS, TestConfig
from .layout import (ANCHOR_SIZE, ID_BUBBLE_R, ID_DIGITS_X0, ID_ROW_PITCH,
                     ID_VALUE_PITCH, MM_PER_PT, OPTION_LETTER_DY, PAGE_DOTS_X0,
                     PAGE_DOTS_PITCH, PAGE_DOTS_Y, PAGE_SIZES, QR_SIZE,
                     SheetLayout)

INK = (0.06, 0.09, 0.16)        # near-black ink for machine zones
LOGO_BRAND = (46 / 255, 90 / 255, 153 / 255)   # #2e5a99 on white paper
LOGO_BRAND_DARKBG = (1.0, 1.0, 1.0)            # white if ever on black
GREY = (0.45, 0.48, 0.55)

HEADER_BASE = {"logo": 15.0, "title": 12.5, "subject": 8.5, "instr": 5.9}
INSTR_DEFAULTS = [
    "Fill one bubble per question using a dark pen or pencil. Erase fully to "
    "change an answer. Do not fold the sheet.",
]

_fonts_registered = False


def register_fonts() -> None:
    """Register bundled fonts with ReportLab (idempotent)."""
    global _fonts_registered
    if _fonts_registered:
        return
    mapping = {
        FONT_OPEN_SANS: FONTS_DIR / "OpenSans-Regular.ttf",
        f"{FONT_OPEN_SANS}-SemiBold": FONTS_DIR / "OpenSans-SemiBold.ttf",
        f"{FONT_OPEN_SANS}-Bold": FONTS_DIR / "OpenSans-Bold.ttf",
        f"{FONT_OPEN_SANS}-ExtraBold": FONTS_DIR / "OpenSans-ExtraBold.ttf",
        # the wordmark ships as both CFF (.otf, for PIL) and TrueType
        # (.ttf, converted by tools/otf2ttf.py — ReportLab embeds TTF only)
        FONT_OPTI: FONTS_DIR / "OPTIBubbleDoubleBold.ttf",
    }
    from reportlab.pdfbase.ttfonts import TTFont
    for name, path in mapping.items():
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
            except Exception:
                pass
    _fonts_registered = True


def _mm(v: float) -> float:
    """mm → reportlab points."""
    return v * MM_PER_PT


def _make_qr(payload: str) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


# ----------------------------------------------------------------------------
# Header auto-fit — the editable zone (title / instructions) may use between
# y = 24 mm (top) and y = 49 mm (brand rule).  Text is shrunk automatically
# until it fits; if even the smallest size fails we refuse (messy > strict).
# ----------------------------------------------------------------------------
def _fit_header(test: TestConfig, pw: float) -> Tuple[float, List[str], float]:
    """Return (font_scale, instruction_lines, title_font_pt).

    Raises ValueError with a friendly message when the header cannot fit.
    """
    warnings: List[str] = []
    scale = float(test.header_font_scale or 1.0)

    raw = (test.sheet_instructions or "").strip() or " ".join(INSTR_DEFAULTS)
    raw = raw[:240]
    # hard-break pathological no-space runs so nothing can overflow the width
    words = []
    for w in raw.split():
        while len(w) > 44:
            words.append(w[:44])
            w = w[44:]
        words.append(w)
    instr_text = " ".join(words)
    max_lines, zone_top, zone_bottom = 3, 40.6, 48.2     # mm, below the subject line
    shrunk_to = None

    title_font = HEADER_BASE["title"]
    try:
        w = pdfmetrics.stringWidth(test.title, f"{FONT_OPEN_SANS}-Bold", title_font * scale)
    except Exception:
        w = 0.0
    max_title_w = (pw - 46.0 - 24.0 - 38.0) * 0.98       # between wordmark and QR
    if w > max_title_w:
        title_font = max(7.5, title_font * max_title_w / w)
        warnings.append("Title was auto-shrunk to fit the header width.")

    while True:
        lines = simpleSplit(instr_text, FONT_OPEN_SANS,
                            HEADER_BASE["instr"] * scale, (pw - 46 - 24) * 0.94) or [""]
        lh = 2.55 * scale
        if len(lines) <= max_lines and zone_top + lh * len(lines) <= zone_bottom + 0.4:
            break
        if scale <= 0.8 + 1e-6:
            raise ValueError(
                "Header text does not fit. Shorten the instructions or lower the "
                "header text size (80–140%).")
        scale = round(scale - 0.05, 2)
        shrunk_to = int(scale * 100)
    if shrunk_to is not None:
        warnings.append(f"Header text auto-shrunk to {shrunk_to}% to keep the "
                        "answer area clear.")
    return scale, lines, title_font


# ----------------------------------------------------------------------------
def generate_sheet_pdf(test: TestConfig, out_path: Path,
                       layout: Optional[SheetLayout] = None) -> Tuple[Path, SheetLayout]:
    """Render the printable answer sheet. Returns (pdf_path, layout)."""
    register_fonts()
    lay = layout or SheetLayout.build(test)
    pw, ph = PAGE_SIZES[lay.page_size]

    h_scale, instr_lines, title_font = _fit_header(test, pw)
    if h_scale < test.header_font_scale - 1e-6 or title_font < HEADER_BASE["title"]:
        lay.warnings.append("Some header text was auto-shrunk to avoid overlapping "
                            "the answer area.")

    c = rl_canvas.Canvas(str(out_path), pagesize=(_mm(pw), _mm(ph)))
    c.setTitle(f"OPTIBubble — {test.title}")
    c.setAuthor("OPTIBubble")

    logo_right = test.logo_position == "right"
    logo_x, qr_x1 = (24.0, pw - 42.0) if not logo_right else (pw - 24.0, 20.0)

    # ------------------------------------------------------------------- QR
    qr_payload = json.dumps({"v": 1, "t": test.test_id, "s": test.session_token, "p": 1})
    qr_img = _make_qr(qr_payload)
    qr_y1 = 28.0
    c.drawImage(ImageReader(qr_img), _mm(qr_x1), _mm(ph - qr_y1 - QR_SIZE),
                width=_mm(QR_SIZE), height=_mm(QR_SIZE),
                preserveAspectRatio=True, mask=None)
    c.setFont(FONT_OPEN_SANS, 5.2)
    c.setFillColorRGB(*GREY)
    c.drawCentredString(_mm(qr_x1 + QR_SIZE / 2), _mm(ph - qr_y1 - QR_SIZE - 3.0),
                        test.test_id)

    # -------------------------------------------------------------- anchors
    c.setFillColorRGB(*INK)
    for (ax, ay) in lay.anchors:
        c.rect(_mm(ax - ANCHOR_SIZE / 2), _mm(ph - ay - ANCHOR_SIZE / 2),
               _mm(ANCHOR_SIZE), _mm(ANCHOR_SIZE), stroke=0, fill=1)

    # --------------------------------------------------- wordmark (#2e5a99)
    try:
        c.setFont(FONT_OPTI, HEADER_BASE["logo"] * h_scale)
    except Exception:
        c.setFont(f"{FONT_OPEN_SANS}-Bold", 12)
    c.setFillColorRGB(*LOGO_BRAND)
    if logo_right:
        # NB: stringWidth returns POINTS — keep it out of the mm arithmetic
        w_pt = pdfmetrics.stringWidth("OPTIBubble", FONT_OPTI,
                                      HEADER_BASE["logo"] * h_scale)
        c.drawString(_mm(pw - 24.0) - w_pt, _mm(ph - 34.0), "OPTIBubble")
    else:
        c.drawString(_mm(24.0), _mm(ph - 34.0), "OPTIBubble")

    # ---------------------------------------------------- title + subject
    c.setFillColorRGB(*INK)
    c.setFont(f"{FONT_OPEN_SANS}-Bold", title_font * h_scale)
    c.drawCentredString(_mm(pw / 2 + 10), _mm(ph - 33.5), test.title[:52])
    c.setFont(FONT_OPEN_SANS, HEADER_BASE["subject"] * h_scale)
    c.setFillColorRGB(*GREY)
    c.drawCentredString(_mm(pw / 2 + 10), _mm(ph - 39.5),
                        f"Subject: {test.subject}  •  {test.num_questions} questions  "
                        f"•  Choose ONE option per question")

    # --------------------------------------------------------- instructions
    c.setFont(FONT_OPEN_SANS, HEADER_BASE["instr"] * h_scale)
    y_instr = 40.6
    for line in instr_lines:
        c.drawString(_mm(24.0), _mm(ph - y_instr), line)
        y_instr += 2.55 * h_scale

    # brand rule (#2e5a99)
    c.setStrokeColorRGB(*LOGO_BRAND)
    c.setLineWidth(0.8)
    c.line(_mm(22.0), _mm(ph - 49.0), _mm(pw - 46.0), _mm(ph - 49.0))

    # ------------------------------------------------------------ page dots
    mask = lay.filled_page_dot_mask()
    for dot in lay.page_dots:
        filled = dot.bit is not None and (mask >> dot.bit) & 1
        if filled:
            c.setFillColorRGB(*INK)
            c.circle(_mm(dot.cx), _mm(ph - dot.cy), _mm(dot.r), stroke=0, fill=1)
        else:
            c.setStrokeColorRGB(*INK)
            c.setLineWidth(0.5)
            c.circle(_mm(dot.cx), _mm(ph - dot.cy), _mm(dot.r), stroke=1, fill=0)
    c.setFont(FONT_OPEN_SANS, 5.0)
    c.setFillColorRGB(*GREY)
    c.drawString(_mm(PAGE_DOTS_X0 + 4 * 5.0 + 2.0), _mm(ph - PAGE_DOTS_Y - 1.2),
                 "sheet code")

    # ----------------------------------------------------------- student ID
    if lay.student_id_digits > 0:
        c.setFillColorRGB(*INK)
        c.setFont(f"{FONT_OPEN_SANS}-Bold", 7.5)
        c.drawString(_mm(22.0), _mm(ph - 70.5), "STUDENT ID")
        c.setFont(FONT_OPEN_SANS, 5.6)
        c.setFillColorRGB(*GREY)
        c.drawString(_mm(22.0), _mm(ph - 75.0), "fill one bubble")
        c.drawString(_mm(22.0), _mm(ph - 78.5), "per row")
        c.setFont(FONT_OPEN_SANS, 5.0)
        for v in range(10):
            c.drawCentredString(_mm(ID_DIGITS_X0 + v * ID_VALUE_PITCH),
                                _mm(ph - 64.5), str(v))
        for d in range(lay.student_id_digits):
            y = 66.5 + d * ID_ROW_PITCH
            c.drawRightString(_mm(ID_DIGITS_X0 - 3.0), _mm(ph - y - 1.0), f"#{d + 1}")

    # -------------------------------------------------------------- bubbles
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.9)
    for b in lay.bubbles:
        if b.kind == "option":
            c.circle(_mm(b.cx), _mm(ph - b.cy), _mm(b.r), stroke=1, fill=0)
        elif b.kind == "digit":
            c.setLineWidth(0.7)
            c.circle(_mm(b.cx), _mm(ph - b.cy), _mm(ID_BUBBLE_R), stroke=1, fill=0)
            c.setLineWidth(0.9)

    # question numbers + option letters
    c.setFillColorRGB(*INK)
    for blk in lay.questions:
        c.setFont(f"{FONT_OPEN_SANS}-SemiBold", 6.8)
        c.drawRightString(_mm(blk.label_cx + 4.0), _mm(ph - blk.y - 1.4), str(blk.q))
        c.setFont(FONT_OPEN_SANS, 5.2)
        c.setFillColorRGB(*GREY)
        for oi in range(blk.n_options):
            c.drawCentredString(_mm(blk.bubble_x0 + oi * blk.bubble_pitch),
                                _mm(ph - blk.y - OPTION_LETTER_DY), LETTERS[oi])
        c.setFillColorRGB(*INK)

    # column separator (subtle) for multi-column sheets
    if lay.columns > 1:
        c.setStrokeColorRGB(0.85, 0.87, 0.90)
        c.setLineWidth(0.4)
        margin = 12.0
        col_w = (pw - 2 * margin) / lay.columns
        for ci in range(1, lay.columns):
            x = margin + ci * col_w
            c.line(_mm(x - 2.0), _mm(ph - (lay.questions_top - 4)),
                   _mm(x - 2.0), _mm(ph - (lay.page_h - 20.0)))

    # ---------------------------------------------------------------- footer
    c.setFont(FONT_OPEN_SANS, 6.0)
    c.setFillColorRGB(*GREY)
    c.drawCentredString(_mm(pw / 2), _mm(9.0),
                        f"OPTIBubble  •  {test.test_id}  •  "
                        f"{lay.num_questions} questions  •  Page 1 of 1")
    try:
        c.setFont(FONT_OPTI, 7)
        c.setFillColorRGB(*LOGO_BRAND)
        c.drawString(_mm(24.0), _mm(7.5), "OPTIBubble")
    except Exception:
        pass

    c.showPage()
    c.save()
    return Path(out_path), lay


def render_pdf_preview(pdf_path: Path, out_png: Path, dpi: int = 150) -> Optional[Path]:
    """Rasterise page 1 of the PDF for on-screen preview (needs PyMuPDF)."""
    try:
        import pymupdf  # optional dependency
        doc = pymupdf.open(str(pdf_path))
        page = doc[0]
        pix = page.get_pixmap(dpi=dpi)
        pix.save(str(out_png))
        return out_png
    except Exception:
        return None
