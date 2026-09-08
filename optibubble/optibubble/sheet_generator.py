"""
Printable answer-sheet PDF generator (ReportLab).

Draws the sheet using the exact geometry from :mod:`optibubble.layout`, so the
OpenCV engine can find every bubble at a known position after perspective
correction.  The sheet includes:

* four solid 10 mm alignment squares (one in each corner),
* a QR code identifying the test session,
* the OPTIBubble wordmark (OPTIBubbleDoubleBold) in brand blue #2e5a99,
* an **obstacle-aware header**: title, subject and instructions are laid out
  around the wordmark/QR blocks and *proven* non-overlapping before the PDF
  is written (`validate_header_boxes`),
* handwritten write-in fields (Name / Class / Date …) — decorative, ignored
  by the scanner,
* binary page-code dots, a student-ID grid, and up to 102 questions.

The answer key may be defined *after* printing — sheets generate fine with a
partial key; grading simply scores only the questions that have one.
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
from .layout import (ANCHOR_SIZE, HEADER_LEFT, HEADER_RIGHT_INSET,
                     HEADER_RULE_Y, ID_BUBBLE_R, ID_DIGITS_X0, ID_ROW_PITCH,
                     ID_VALUE_PITCH, MM_PER_PT, OPTION_LETTER_DY,
                     PAGE_DOTS_PITCH, PAGE_DOTS_X0, PAGE_DOTS_Y,
                     PAGE_SIZES, QR_SIZE, SheetLayout, validate_header_boxes)

INK = (0.06, 0.09, 0.16)        # near-black ink for machine zones
LOGO_BRAND = (46 / 255, 90 / 255, 153 / 255)   # #2e5a99 on white paper
GREY = (0.45, 0.48, 0.55)

HEADER_BASE = {"logo": 15.0, "title": 12.5, "subject": 8.5, "instr": 5.9,
               "field_label": 6.5}
INSTR_DEFAULT = ("Fill one bubble per question using a dark pen or pencil. "
                 "Erase fully to change an answer. Do not fold the sheet.")

# vertical bands (mm from the top)
TITLE_Y = 31.5          # title baseline
SUBJECT_Y = 38.0        # subject baseline
INSTR_TOP = 41.0
INSTR_BOTTOM = 48.0
QR_TOP = 28.0
LOGO_Y = 31.0           # wordmark baseline

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


def _sw(text: str, font: str, size_pt: float) -> float:
    """stringWidth in points → mm."""
    try:
        return pdfmetrics.stringWidth(text, font, size_pt) / MM_PER_PT
    except Exception:
        return len(text) * size_pt * 0.5 / MM_PER_PT


def _wrap(text: str, font: str, size_pt: float, max_w_mm: float) -> List[str]:
    return simpleSplit(text, font, size_pt, max_w_mm * MM_PER_PT) or [""]


# ----------------------------------------------------------------------------
# Header geometry — compute every element's box first, prove they are
# collision-free, then draw.  Nothing may cross into the answer area below
# HEADER_RULE_Y + the write-in/ID furniture.
# ----------------------------------------------------------------------------
def _plan_header(test: TestConfig, lay: SheetLayout
                 ) -> dict:  # noqa: C901 (clarity over cyclomatic count)
    pw = lay.page_w
    logo_right = test.logo_position == "right"
    scale = float(test.header_font_scale or 1.0)
    warnings: List[str] = []

    logo_pt = HEADER_BASE["logo"] * scale
    logo_w = _sw("OPTIBubble", FONT_OPTI, logo_pt)
    pw_right = pw - HEADER_RIGHT_INSET

    if logo_right:
        logo_box = (pw_right - logo_w, LOGO_Y - 5.5, pw_right, LOGO_Y + 2.5)
        qr_x0 = HEADER_LEFT
    else:
        logo_box = (HEADER_LEFT, LOGO_Y - 5.5, HEADER_LEFT + logo_w, LOGO_Y + 2.5)
        qr_x0 = pw_right - QR_SIZE
    qr_box = (qr_x0, QR_TOP, qr_x0 + QR_SIZE, QR_TOP + QR_SIZE)

    # clear centred zone between the two side blocks
    left_edge = max(b[2] for b in (logo_box, qr_box) if b[0] < pw / 2) + 4.0
    right_edge = min(b[0] for b in (logo_box, qr_box) if b[2] > pw / 2) - 4.0
    centre = (left_edge + right_edge) / 2.0
    zone_w = right_edge - left_edge

    # ---- title: shrink to fit the clear zone ------------------------------
    title_font = HEADER_BASE["title"] * scale
    title_txt = test.title[:52] or "Untitled Test"
    while _sw(title_txt, f"{FONT_OPEN_SANS}-Bold", title_font) > zone_w and title_font > 7.5:
        title_font -= 0.25
    if title_font < HEADER_BASE["title"] * scale - 1e-6:
        warnings.append("Title was auto-shrunk to fit the header.")
    tw = _sw(title_txt, f"{FONT_OPEN_SANS}-Bold", title_font)
    title_box = (centre - tw / 2, TITLE_Y - 3.2 * scale,
                 centre + tw / 2, TITLE_Y + 2.2)

    # ---- subject: single line, clamped -------------------------------------
    subject_font = HEADER_BASE["subject"] * scale
    subj_txt = (f"Subject: {test.subject}  •  {test.num_questions} questions  "
                f"•  Choose ONE option per question")
    subj_line = _wrap(subj_txt, FONT_OPEN_SANS, subject_font, zone_w)[0]
    if subj_line != subj_txt:
        subj_line += "…"
    sw_ = _sw(subj_line, FONT_OPEN_SANS, subject_font)
    subject_box = (centre - sw_ / 2, SUBJECT_Y - 2.4,
                   centre + sw_ / 2, SUBJECT_Y + 1.8)

    # ---- instructions: avoid the QR column, shrink until ≤3 lines ---------
    instr_text = (test.sheet_instructions or "").strip() or INSTR_DEFAULT
    raw = instr_text[:240]
    words = []
    for w in raw.split():
        while len(w) > 40:
            words.append(w[:40])
            w = w[40:]
        words.append(w)
    instr_text = " ".join(words)

    if qr_box[0] < pw / 2:              # QR on the left → start right of it
        ix0, ix1 = qr_box[2] + 4.0, pw_right
    else:                               # QR on the right → stop before it
        ix0, ix1 = HEADER_LEFT, qr_box[0] - 4.0
    iw = ix1 - ix0

    shrunk_to = None
    lines = _wrap(instr_text, FONT_OPEN_SANS, HEADER_BASE["instr"] * scale, iw)
    while (len(lines) > 3 or INSTR_TOP + 2.55 * scale * len(lines) > INSTR_BOTTOM + 0.4):
        if scale <= 0.8 + 1e-6:
            raise ValueError(
                "Header text does not fit. Shorten the instructions or lower "
                "the header text size (80–140%).")
        scale = round(scale - 0.05, 2)
        shrunk_to = int(scale * 100)
        lines = _wrap(instr_text, FONT_OPEN_SANS, HEADER_BASE["instr"] * scale, iw)
    if shrunk_to:
        warnings.append(f"Header text auto-shrunk to {shrunk_to}% to keep the "
                        "answer area clear.")
    instr_h = 2.55 * scale * len(lines)
    instr_box = (ix0, INSTR_TOP, ix1, INSTR_TOP + instr_h)

    # ---- write-in fields band (decorative) --------------------------------
    fields = test.write_in_field_list()
    field_boxes = []
    if fields:
        cols, x0, x1 = 3, HEADER_LEFT + 4.0, PAGE_DOTS_X0 - 8.0
        col_w = (x1 - x0) / cols
        for i, label in enumerate(fields):
            r, cidx = divmod(i, cols)
            fx = x0 + cidx * col_w
            fy = 52.0 + r * 5.4
            # the box is the *drawn* extent: label + underline, not the cell
            field_boxes.append((f"field:{label}", fx, fy, fx + col_w - 2.5,
                                fy + 5.0))

    boxes = ([("wordmark", *logo_box), ("QR", *qr_box),
              ("title", *title_box), ("subject", *subject_box),
              ("instructions", *instr_box)] +
             [("page-dots", PAGE_DOTS_X0, PAGE_DOTS_Y - 2,
               PAGE_DOTS_X0 + 4 * PAGE_DOTS_PITCH, PAGE_DOTS_Y + 2)] +
             field_boxes)
    validate_header_boxes(boxes)        # raises LayoutError on any overlap

    return {"scale": scale, "logo_right": logo_right, "logo_pt": logo_pt,
            "logo_box": logo_box, "qr_box": qr_box, "centre": centre,
            "title_txt": title_txt, "title_font": title_font,
            "subj_txt": subj_line, "subject_font": subject_font,
            "instr_lines": lines, "instr_scale": scale,
            "instr_x": ix0, "fields": fields, "warnings": warnings}


# ----------------------------------------------------------------------------
def generate_sheet_pdf(test: TestConfig, out_path: Path,
                       layout: Optional[SheetLayout] = None) -> Tuple[Path, SheetLayout]:
    """Render the printable answer sheet. Returns (pdf_path, layout)."""
    register_fonts()
    lay = layout or SheetLayout.build(test)
    pw, ph = PAGE_SIZES[lay.page_size]
    plan = _plan_header(test, lay)
    lay.warnings.extend(plan["warnings"])

    c = rl_canvas.Canvas(str(out_path), pagesize=(_mm(pw), _mm(ph)))
    c.setTitle(f"OPTIBubble — {test.title}")
    c.setAuthor("OPTIBubble")

    # ------------------------------------------------------------------- QR
    qr_payload = json.dumps({"v": 1, "t": test.test_id, "s": test.session_token, "p": 1})
    qr_img = _make_qr(qr_payload)
    qx, qy = plan["qr_box"][0], plan["qr_box"][1]
    c.drawImage(ImageReader(qr_img), _mm(qx), _mm(ph - qy - QR_SIZE),
                width=_mm(QR_SIZE), height=_mm(QR_SIZE),
                preserveAspectRatio=True, mask=None)
    c.setFont(FONT_OPEN_SANS, 5.2)
    c.setFillColorRGB(*GREY)
    c.drawCentredString(_mm(qx + QR_SIZE / 2), _mm(ph - qy - QR_SIZE - 3.0),
                        test.test_id)

    # -------------------------------------------------------------- anchors
    c.setFillColorRGB(*INK)
    for (ax, ay) in lay.anchors:
        c.rect(_mm(ax - ANCHOR_SIZE / 2), _mm(ph - ay - ANCHOR_SIZE / 2),
               _mm(ANCHOR_SIZE), _mm(ANCHOR_SIZE), stroke=0, fill=1)

    # ------------------------------------------------ wordmark (#2e5a99)
    try:
        c.setFont(FONT_OPTI, plan["logo_pt"])
    except Exception:
        c.setFont(f"{FONT_OPEN_SANS}-Bold", 12)
    c.setFillColorRGB(*LOGO_BRAND)
    c.drawString(_mm(plan["logo_box"][0]), _mm(ph - LOGO_Y), "OPTIBubble")

    # -------------------------------------------- title / subject / notes
    c.setFillColorRGB(*INK)
    c.setFont(f"{FONT_OPEN_SANS}-Bold", plan["title_font"])
    c.drawCentredString(_mm(plan["centre"]), _mm(ph - TITLE_Y), plan["title_txt"])
    c.setFont(FONT_OPEN_SANS, plan["subject_font"])
    c.setFillColorRGB(*GREY)
    c.drawCentredString(_mm(plan["centre"]), _mm(ph - SUBJECT_Y), plan["subj_txt"])

    c.setFont(FONT_OPEN_SANS, HEADER_BASE["instr"] * plan["instr_scale"])
    y_instr = INSTR_TOP
    for line in plan["instr_lines"]:
        c.drawString(_mm(plan["instr_x"]), _mm(ph - y_instr), line)
        y_instr += 2.55 * plan["instr_scale"]

    # brand rule
    c.setStrokeColorRGB(*LOGO_BRAND)
    c.setLineWidth(0.8)
    c.line(_mm(HEADER_LEFT), _mm(ph - HEADER_RULE_Y),
           _mm(pw - HEADER_RIGHT_INSET), _mm(ph - HEADER_RULE_Y))

    # ------------------------------------------------- write-in fields band
    if plan["fields"]:
        cols, x0, x1 = 3, HEADER_LEFT + 4.0, PAGE_DOTS_X0 - 8.0
        col_w = (x1 - x0) / cols
        for i, label in enumerate(plan["fields"]):
            r, cidx = divmod(i, cols)
            fx = x0 + cidx * col_w
            fy = 52.0 + r * 5.4
            c.setFont(f"{FONT_OPEN_SANS}-Bold", HEADER_BASE["field_label"])
            c.setFillColorRGB(*INK)
            c.drawString(_mm(fx), _mm(ph - fy - 3.2), label)
            lw = _sw(label, f"{FONT_OPEN_SANS}-Bold", HEADER_BASE["field_label"])
            c.setStrokeColorRGB(0.55, 0.58, 0.64)
            c.setLineWidth(0.5)
            c.line(_mm(fx + lw + 1.5), _mm(ph - fy - 3.6),
                   _mm(fx + col_w - 2.0), _mm(ph - fy - 3.6))

    # ------------------------------------------------------------ page dots
    mask = lay.filled_page_dot_mask()
    for dot in lay.page_dots:
        dx = PAGE_DOTS_X0 + (dot.bit or 0) * PAGE_DOTS_PITCH
        filled = dot.bit is not None and (mask >> dot.bit) & 1
        if filled:
            c.setFillColorRGB(*INK)
            c.circle(_mm(dx), _mm(ph - PAGE_DOTS_Y), _mm(dot.r), stroke=0, fill=1)
        else:
            c.setStrokeColorRGB(*INK)
            c.setLineWidth(0.5)
            c.circle(_mm(dx), _mm(ph - PAGE_DOTS_Y), _mm(dot.r), stroke=1, fill=0)
    c.setFont(FONT_OPEN_SANS, 5.0)
    c.setFillColorRGB(*GREY)
    c.drawString(_mm(PAGE_DOTS_X0 + 4 * PAGE_DOTS_PITCH + 2.0),
                 _mm(ph - PAGE_DOTS_Y - 1.2), "sheet code")

    # ----------------------------------------------------------- student ID
    if lay.student_id_digits > 0:
        c.setFillColorRGB(*INK)
        c.setFont(f"{FONT_OPEN_SANS}-Bold", 7.5)
        c.drawString(_mm(HEADER_LEFT + 2.0), _mm(ph - 70.5), "STUDENT ID")
        c.setFont(FONT_OPEN_SANS, 5.6)
        c.setFillColorRGB(*GREY)
        c.drawString(_mm(HEADER_LEFT + 2.0), _mm(ph - 75.0), "fill one bubble")
        c.drawString(_mm(HEADER_LEFT + 2.0), _mm(ph - 78.5), "per row")
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
        c.drawString(_mm(HEADER_LEFT), _mm(7.5), "OPTIBubble")
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


# ----------------------------------------------------------------------------
# Answer-key PDF — the teacher's companion sheet
# ----------------------------------------------------------------------------
def generate_key_pdf(test: TestConfig, out_path: Path) -> Path:
    """One-page answer key: header + column grid of Q#→letter + compact string."""
    from .layout import PAGE_SIZES
    pw, ph = PAGE_SIZES.get(test.page_size, PAGE_SIZES["a4"])
    c = rl_canvas.Canvas(str(out_path), pagesize=(_mm(pw), _mm(ph)))
    c.setTitle(f"Answer Key — {test.title}")
    c.setAuthor("OPTIBubble")

    register_fonts()
    letters = LETTERS[: test.options_per_question]

    # header
    try:
        c.setFont(FONT_OPTI, 15)
    except Exception:
        c.setFont(f"{FONT_OPEN_SANS}-Bold", 12)
    c.setFillColorRGB(*LOGO_BRAND)
    c.drawString(_mm(20), _mm(ph - 22), "OPTIBubble")

    c.setFillColorRGB(*INK)
    c.setFont(f"{FONT_OPEN_SANS}-ExtraBold", 16)
    c.drawString(_mm(20), _mm(ph - 36), "ANSWER KEY")
    c.setFont(FONT_OPEN_SANS, 8.5)
    c.setFillColorRGB(*GREY)
    c.drawString(_mm(20), _mm(ph - 42),
                 f"{test.title}  ·  {test.subject}  ·  {test.num_questions} questions"
                 f"  ·  {test.test_id}")
    import time as _t
    c.drawRightString(_mm(pw - 20), _mm(ph - 42), _t.strftime("%Y-%m-%d %H:%M"))

    c.setStrokeColorRGB(*LOGO_BRAND)
    c.setLineWidth(0.8)
    c.line(_mm(20), _mm(ph - 47), _mm(pw - 20), _mm(ph - 47))

    # grid of answers
    entries = sorted((int(q), a) for q, a in (test.answer_key or {}).items())
    per_col = 30
    cols = max(1, min(4, -(-len(entries) // per_col))) if entries else 1
    col_w = (pw - 40) / cols
    y0 = ph - 58
    row_h = 6.2
    for i, (q, a) in enumerate(entries):
        col, row = divmod(i, per_col)
        x = 20 + col * col_w
        y = y0 - row * row_h
        c.setFont(f"{FONT_OPEN_SANS}-SemiBold", 9)
        c.setFillColorRGB(*GREY)
        c.drawRightString(_mm(x + 8), _mm(y), f"{q}")
        c.setFont(f"{FONT_OPEN_SANS}-ExtraBold", 10.5)
        c.setFillColorRGB(*INK)
        c.drawString(_mm(x + 12), _mm(y), str(a).upper())

    # compact one-line key
    if entries:
        compact = " ".join(a for _, a in entries)
        c.setFont(FONT_OPEN_SANS, 7.5)
        c.setFillColorRGB(*GREY)
        c.drawString(_mm(20), _mm(24),
                     "Compact (order Q1→Q" + str(len(entries)) + "):  " + compact[:150])

    # "for grading use" bubble strip of the key itself
    y = 16
    c.setFont(FONT_OPEN_SANS, 6)
    c.setFillColorRGB(*GREY)
    c.drawString(_mm(20), _mm(30),
                 f"Valid options: A–{letters[-1]} · grading scores defined questions only")
    try:
        c.setFont(FONT_OPTI, 7)
        c.setFillColorRGB(*LOGO_BRAND)
        c.drawString(_mm(20), _mm(10), "OPTIBubble")
    except Exception:
        pass
    c.showPage()
    c.save()
    return Path(out_path)
