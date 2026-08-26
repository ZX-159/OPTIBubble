"""
Sheet geometry — the single source of truth shared by the PDF generator and
the OpenCV grading engine.

All coordinates are in **millimetres from the top-left corner** of the page.
The generator draws primitives at these exact positions; the engine warps the
photograph onto the same coordinate space and then samples the bubbles at the
same positions.  Because both sides import this module, a bubble can never
"move" between printing and grading.

Page anatomy (single sheet, up to 3 question columns → up to 102 questions):

    ┌────────────────────────────────────────────┐
    │ ■ anchor                                   │  ■ = 10 mm solid alignment squares
    │  OPTIBubble   TITLE / SUBJECT      [QR]    │
    │                 ···· page-code dots ····   │
    │  STUDENT ID  ▫▫▫▫▫▫▫▫▫▫  (7 rows × 0-9)   │
    │                                             │
    │  1  ⓐ ⓑ ⓒ ⓓ ⓔ        35  ⓐ ⓑ ⓒ ⓓ ⓔ        │
    │  2  ⓐ ⓑ ⓒ ⓓ ⓔ        36  ⓐ ⓑ ⓒ ⓓ ⓔ        │
    │  …         (column-major question order)   │
    │                                  ■ anchor  │
    │  OPTIBubble • T123456 • Page 1 of 1        │
    │ ■ anchor                                   │
    └────────────────────────────────────────────┘
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .config import LETTERS, TestConfig

MM_PER_PT = 72.0 / 25.4  # reportlab points ↔ mm

PAGE_SIZES: Dict[str, Tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "letter": (215.9, 279.4),
}

# --- fixed furniture --------------------------------------------------------
ANCHOR_SIZE = 10.0          # side of the solid alignment squares (mm)
ANCHOR_INSET = 15.0         # anchor-centre distance from page edges
QR_SIZE = 22.0              # QR code square (top-right of the header)
ID_DIGITS_X0 = 50.0         # first value-column centre of the student-ID strip
ID_VALUE_PITCH = 5.6        # horizontal pitch of values 0..9
ID_ROW_PITCH = 4.3          # vertical pitch of digit rows
ID_BUBBLE_R = 1.55
PAGE_DOTS_Y = 58.5          # page-code dots row
PAGE_DOTS_X0 = 50.0
PAGE_DOTS_PITCH = 5.0
PAGE_DOTS_R = 1.35
QUESTIONS_TOP = 104.0
QUESTIONS_BOTTOM_MARGIN = 21.0
QUESTION_PITCH_MAX = 5.2
QUESTION_PITCH_MIN = 4.2
BUBBLE_R_1COL, BUBBLE_R_MULTI = 1.9, 1.78
OPTION_LETTER_DY = 2.9      # option letters printed below bubbles

ROWS_PER_COLUMN_TARGET = 34


@dataclass
class Bubble:
    kind: str            # "option" | "digit" | "pagedot"
    cx: float            # centre x (mm)
    cy: float            # centre y (mm)
    r: float             # radius (mm)
    q: Optional[int] = None       # question number (1-based)
    option: Optional[int] = None  # option index 0-based
    digit: Optional[int] = None   # student-ID digit position (0-based)
    value: Optional[int] = None   # digit value 0-9 (for kind="digit")
    bit: Optional[int] = None     # for kind="pagedot"


@dataclass
class QuestionBlock:
    q: int
    col: int
    row: int
    label_cx: float
    bubble_x0: float
    bubble_pitch: float
    y: float
    r: float
    n_options: int
    page: int = 1

    def bounds(self) -> Tuple[float, float, float, float]:
        """(x0, y0, x1, y1) crop box in mm including the label and letters."""
        return (self.label_cx - 7.0,
                self.y - 3.4,
                self.bubble_x0 + (self.n_options - 1) * self.bubble_pitch + 4.0,
                self.y + 4.2)


@dataclass
class SheetLayout:
    """Complete, serialisable geometry of a printed sheet."""

    version: int = 1
    page_size: str = "a4"
    page_w: float = 210.0
    page_h: float = 297.0
    num_questions: int = 20
    options_per_question: int = 4
    columns: int = 1
    student_id_digits: int = 7
    anchors: List[Tuple[float, float]] = field(default_factory=list)  # TL,TR,BR,BL centres
    bubbles: List[Bubble] = field(default_factory=list)               # options + digits
    questions: List[QuestionBlock] = field(default_factory=list)
    page_dots: List[Bubble] = field(default_factory=list)
    questions_top: float = QUESTIONS_TOP      # dynamic — pushed down by long ID grids
    warnings: List[str] = field(default_factory=list)
    test_id: str = ""
    session_token: str = ""

    # ------------------------------------------------------------------
    @staticmethod
    def build(test: TestConfig) -> "SheetLayout":
        pw, ph = PAGE_SIZES.get(test.page_size, PAGE_SIZES["a4"])
        q, k = test.num_questions, test.options_per_question

        columns = 1 if q <= ROWS_PER_COLUMN_TARGET else (
            2 if q <= 2 * ROWS_PER_COLUMN_TARGET else 3)
        rows_needed = math.ceil(q / columns)

        # the ID strip grows with digit count — questions must start below it
        id_bottom = 66.5 + (test.student_id_digits - 1) * ID_ROW_PITCH + ID_BUBBLE_R \
            if test.student_id_digits else 0.0
        questions_top = max(QUESTIONS_TOP, id_bottom + 6.0)

        avail = (ph - QUESTIONS_BOTTOM_MARGIN) - questions_top
        pitch_y = min(QUESTION_PITCH_MAX, avail / rows_needed)
        if pitch_y < QUESTION_PITCH_MIN - 1e-6:
            raise LayoutError(
                f"{q} questions do not fit on a single {test.page_size.upper()} sheet "
                f"with {test.student_id_digits} ID digits. Use fewer questions, fewer "
                f"ID digits, or switch page size.")

        lay = SheetLayout(
            page_size=test.page_size, page_w=pw, page_h=ph,
            num_questions=q, options_per_question=k, columns=columns,
            student_id_digits=test.student_id_digits,
            questions_top=questions_top,
            anchors=[(ANCHOR_INSET, ANCHOR_INSET),
                     (pw - ANCHOR_INSET, ANCHOR_INSET),
                     (pw - ANCHOR_INSET, ph - ANCHOR_INSET),
                     (ANCHOR_INSET, ph - ANCHOR_INSET)],
            test_id=test.test_id, session_token=test.session_token,
        )

        # --- page-code dots (page number encoded in binary) ----------------
        for b in range(4):
            lay.page_dots.append(Bubble("pagedot", PAGE_DOTS_X0 + b * PAGE_DOTS_PITCH,
                                        PAGE_DOTS_Y, PAGE_DOTS_R, bit=b))

        # --- student ID strip (rows = digit positions, cols = 0..9) --------
        for d in range(test.student_id_digits):
            y = 66.5 + d * ID_ROW_PITCH
            for v in range(10):
                lay.bubbles.append(Bubble("digit", ID_DIGITS_X0 + v * ID_VALUE_PITCH,
                                          y, ID_BUBBLE_R, digit=d, value=v))

        # --- question grid (column-major) -----------------------------------
        r = BUBBLE_R_1COL if columns == 1 else BUBBLE_R_MULTI
        margin = 12.0
        col_w = (pw - 2 * margin) / columns
        pitch_x_max = 8.0 if columns == 1 else 7.4
        pitch_x = min(pitch_x_max, (col_w - 20.0) / k)

        for qn in range(1, q + 1):
            col = (qn - 1) // rows_needed
            row = (qn - 1) % rows_needed
            col_x = margin + col * col_w
            label_cx = col_x + 8.0
            bubble_x0 = col_x + 14.5
            y = questions_top + row * pitch_y
            lay.questions.append(QuestionBlock(
                q=qn, col=col, row=row, label_cx=label_cx,
                bubble_x0=bubble_x0, bubble_pitch=pitch_x, y=y, r=r, n_options=k))
            for oi in range(k):
                lay.bubbles.append(Bubble(
                    "option", bubble_x0 + oi * pitch_x, y, r, q=qn, option=oi))

        validate_layout(lay)
        return lay

    # ------------------------------------------------------------------
    def filled_page_dot_mask(self) -> int:
        """Which page-code dots are *printed solid* (always page 1 today)."""
        return 1  # page number 1

    def bubbles_for_question(self, qn: int) -> List[Bubble]:
        return [b for b in self.bubbles if b.kind == "option" and b.q == qn]

    def question_block(self, qn: int) -> Optional[QuestionBlock]:
        for blk in self.questions:
            if blk.q == qn:
                return blk
        return None

    def digit_bubbles(self, digit: int) -> List[Bubble]:
        return [b for b in self.bubbles if b.kind == "digit" and b.digit == digit]

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "page_size": self.page_size, "page_w": self.page_w, "page_h": self.page_h,
            "num_questions": self.num_questions,
            "options_per_question": self.options_per_question,
            "columns": self.columns, "student_id_digits": self.student_id_digits,
            "questions_top": self.questions_top,
            "anchors": self.anchors,
            "page_dot_mask": self.filled_page_dot_mask(),
            "test_id": self.test_id, "session_token": self.session_token,
            "bubbles": [b.__dict__ for b in self.bubbles],
            "questions": [qb.__dict__ for qb in self.questions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SheetLayout":
        lay = cls(page_size=d.get("page_size", "a4"),
                  page_w=d.get("page_w", 210.0), page_h=d.get("page_h", 297.0),
                  num_questions=d.get("num_questions", 20),
                  options_per_question=d.get("options_per_question", 4),
                  columns=d.get("columns", 1),
                  student_id_digits=d.get("student_id_digits", 7),
                  anchors=[tuple(a) for a in d.get("anchors", [])],
                  test_id=d.get("test_id", ""),
                  session_token=d.get("session_token", ""))
        lay.bubbles = [Bubble(**b) for b in d.get("bubbles", [])]
        lay.questions = [QuestionBlock(**qb) for qb in d.get("questions", [])]
        lay.page_dots = [Bubble(**b) for b in d.get("page_dots", [])]
        if not lay.page_dots:
            for b in range(4):
                lay.page_dots.append(Bubble("pagedot", PAGE_DOTS_X0 + b * PAGE_DOTS_PITCH,
                                            PAGE_DOTS_Y, PAGE_DOTS_R, bit=b))
        lay.questions_top = float(d.get("questions_top", QUESTIONS_TOP))
        return lay


# ----------------------------------------------------------------------------
# Layout validation — guarantees a clean, non-overlapping sheet
# ----------------------------------------------------------------------------
class LayoutError(ValueError):
    """Raised when a sheet cannot be laid out without overlaps."""


def validate_layout(lay: SheetLayout) -> List[str]:
    """Geometric sanity checks on a built layout.

    Raises :class:`LayoutError` on any hard problem (overlapping bubbles,
    out-of-page furniture); non-fatal notes live in ``lay.warnings`` so the
    UI can surface them ("header text auto-shrunk", …).
    """
    problems: List[str] = []

    # 1 — every bubble inside the printable area ---------------------------
    for b in lay.bubbles:
        if not (8.0 <= b.cx <= lay.page_w - 8.0 and 18.0 <= b.cy <= lay.page_h - 12.0):
            problems.append(f"Bubble ({b.kind}) at {b.cx:.1f},{b.cy:.1f} mm falls "
                            "outside the printable area.")

    # 2 — no two bubbles overlap (spatial-hash neighbours) ------------------
    cell = 6.0
    grid: Dict[Tuple[int, int], List[Bubble]] = {}
    for b in lay.bubbles:
        grid.setdefault((int(b.cx // cell), int(b.cy // cell)), []).append(b)
    for (gx, gy), bucket in grid.items():
        neighbours: List[Bubble] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbours.extend(grid.get((gx + dx, gy + dy), []))
        for b in bucket:
            for o in neighbours:
                if o is b:
                    continue
                min_d = b.r + o.r + 0.8            # 0.8 mm guaranteed gap
                if ((b.cx - o.cx) ** 2 + (b.cy - o.cy) ** 2) < min_d * min_d:
                    problems.append(f"Bubbles overlap at {b.cx:.1f},{b.cy:.1f} mm "
                                    f"({b.kind} vs {o.kind}).")

    # 3 — question grid clear of the ID strip and the bottom anchors --------
    if lay.questions:
        first_q = min(q.y for q in lay.questions)
        last_q = max(q.y for q in lay.questions) + BUBBLE_R_1COL
        if lay.student_id_digits > 0 and first_q < lay.questions_top - 0.5:
            problems.append("Question grid starts above the student-ID strip.")
        anchor_top = lay.page_h - ANCHOR_INSET - ANCHOR_SIZE / 2
        if last_q > anchor_top - 1.0:
            problems.append("Question grid runs into the bottom alignment squares.")

    # 4 — ID strip must end above the questions ----------------------------
    if lay.student_id_digits > 0 and lay.questions:
        id_bottom = 66.5 + (lay.student_id_digits - 1) * ID_ROW_PITCH + ID_BUBBLE_R
        if id_bottom > lay.questions_top - 1.0:
            problems.append("Student-ID strip overlaps the question area.")

    if problems:
        raise LayoutError("Sheet layout invalid: " + "; ".join(problems[:4]))
    return lay.warnings
