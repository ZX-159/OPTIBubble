"""
OpenCV OMR engine — detects the sheet, flattens it, reads every bubble and
grades the test with per-question confidence scoring.

Pipeline
--------
1.  Decode + validate the photo (resolution, exposure).
2.  Binarise (Otsu) and locate the four solid corner squares.
3.  Verify the quadrilateral looks like the printed page, then apply a
    perspective transform onto a canonical top-down raster.
4.  Sample the *inner disc* of every bubble and compute the dark-pixel ratio.
5.  Apply the confidence model:

    * top density  < t_blank              → BLANK  (unanswered)
    * top density  < t_fill               → FAINT  (stray / partial mark)
    * 2nd density ≥ max(t_fill, top×ratio)→ MULTI  (double-marked)
    * top density  < faint_upper          → FAINT  (light pen / partial erase)
    * otherwise                           → confident auto-grade

6.  Anything flagged produces a cropped PNG for the desktop review queue.
"""

from __future__ import annotations

import itertools
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .config import AdvancedSettings, LETTERS, TestConfig
from .layout import (ANCHOR_SIZE, ID_DIGITS_X0, ID_ROW_PITCH, ID_VALUE_PITCH,
                     SheetLayout)

ANCHOR_REF_R_MM = ANCHOR_SIZE * 0.35   # inner core of a solid anchor square


# ----------------------------------------------------------------------------
class OMRReject(Exception):
    """Photo cannot be graded — carry a machine code + friendly message."""

    def __init__(self, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


@dataclass
class Flag:
    kind: str            # BLANK | MULTI | FAINT | ID
    q: Optional[int]     # question number, None for student-ID issues
    digit: Optional[int] = None
    guess: Optional[str] = None
    message: str = ""
    crop: str = ""       # path to cropped PNG


@dataclass
class GradeResult:
    sheet_id: str
    ts: str
    page: int = 1
    student_id: str = ""
    answers: Dict[int, Optional[str]] = field(default_factory=dict)
    correct: Dict[int, bool] = field(default_factory=dict)
    score: float = 0
    max_score: float = 0
    partials: List[int] = field(default_factory=list)
    confidence: float = 1.0
    flags: List[Flag] = field(default_factory=list)
    status: str = "auto"                     # auto | review
    image_path: str = ""
    duration_ms: int = 0

    def summary(self) -> dict:
        return {
            "sheet_id": self.sheet_id, "student_id": self.student_id,
            "status": self.status, "score": self.score, "max": self.max_score,
            "confidence": round(self.confidence, 3),
            "flags": [{"kind": f.kind, "q": f.q, "digit": f.digit,
                       "guess": f.guess, "message": f.message} for f in self.flags],
        }


# ----------------------------------------------------------------------------
# Image loading / validation
# ----------------------------------------------------------------------------
def load_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise OMRReject("BAD_IMAGE", "The uploaded file is not a readable image.",
                        "Retake the photo and try again.")
    return img


def quick_validate(img: np.ndarray, s: AdvancedSettings) -> None:
    h, w = img.shape[:2]
    if min(h, w) < s.min_photo_dim_px:
        raise OMRReject(
            "LOW_RES", f"Photo resolution too low ({w}×{h}px).",
            "Move closer to the sheet or wipe the camera lens.")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean = float(gray.mean())
    if mean < 35:
        raise OMRReject("TOO_DARK", "Photo is too dark.",
                        "Turn on more lights or use the torch button.")
    if mean > 242:
        raise OMRReject("TOO_BRIGHT", "Photo is overexposed.",
                        "Avoid direct flashlight glare on the paper.")


# ----------------------------------------------------------------------------
# Corner-square detection
# ----------------------------------------------------------------------------
def order_corners(pts: np.ndarray) -> Tuple[np.ndarray, float]:
    """Order 4 points as TL, TR, BR, BL and return aspect (w/h)."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    tl, br = pts[np.argmin(s)], pts[np.argmax(s)]
    tr, bl = pts[np.argmin(d)], pts[np.argmax(d)]
    ordered = np.array([tl, tr, br, bl], dtype=np.float32)
    top_w = float(np.linalg.norm(tr - tl))
    bot_w = float(np.linalg.norm(br - bl))
    lef_h = float(np.linalg.norm(bl - tl))
    rig_h = float(np.linalg.norm(br - tr))
    w = max(top_w, bot_w)
    h = max(lef_h, rig_h)
    return ordered, (w / h if h > 0 else 0.0)


def _candidate_squares(bw: np.ndarray, img_area: float,
                       relaxed: bool = False) -> List[Tuple[float, np.ndarray]]:
    """Scan a binarised image for solid, roughly-square 4-gon contours.

    ``relaxed`` widens the area / aspect / extent windows for the fallback
    passes used when the primary (Otsu) detection is defeated by glare or a
    shadow crossing a corner — it only ever runs after the strict pass failed,
    so it can never disturb a clean detection.
    """
    contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if relaxed:
        area_lo, area_hi = 0.00006 * img_area, 0.028 * img_area
        ar_lo, ar_hi, extr = 0.40, 2.2, 0.60
    else:
        area_lo, area_hi = 0.00008 * img_area, 0.02 * img_area
        ar_lo, ar_hi, extr = 0.55, 1.8, 0.72
    cands: List[Tuple[float, np.ndarray]] = []
    for cnt in contours:
        a = cv2.contourArea(cnt)
        if not (area_lo < a < area_hi):
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        if len(approx) != 4:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        if w == 0 or h == 0:
            continue
        aspect = w / float(h)
        if not (ar_lo < aspect < ar_hi):
            continue
        extent = a / float(w * h)                 # solid squares only
        if extent < extr:
            continue
        M = cv2.moments(approx)
        if M["m00"] == 0:
            continue
        cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
        cands.append((a, np.array([cx, cy], dtype=np.float32)))
    return cands


def _select_quad(cands: List[Tuple[float, np.ndarray]]
                 ) -> Optional[np.ndarray]:
    """Pick the most page-like quadrilateral from anchor-square candidates.

    Returns ordered (TL, TR, BR, BL) corners or ``None`` if no 4-point
    combination looks like the printed sheet.  Shared by every detection
    pass so the geometry sanity checks are identical.
    """
    if len(cands) < 4:
        return None
    cands = sorted(cands, key=lambda t: -t[0])[:12]
    best, best_area = None, -1.0
    for combo in itertools.combinations(range(len(cands)), 4):
        pts = np.array([cands[i][1] for i in combo], dtype=np.float32)
        ordered, aspect = order_corners(pts)
        if not (0.52 < aspect < 1.15):            # portrait page-ish (A4 = 0.707)
            continue
        tl, tr, br, bl = ordered
        d1 = np.linalg.norm(tl - br)
        d2 = np.linalg.norm(tr - bl)
        if d2 == 0 or abs(d1 - d2) / max(d1, d2) > 0.30:   # diagonals ≈ equal
            continue
        area = d1 * d2 / 2
        if area > best_area:
            best, best_area = ordered, area
    return best


def find_page_corners(gray: np.ndarray) -> np.ndarray:
    """Locate the four alignment squares. Returns ordered (TL,TR,BR,BL).

    Detection runs on a ≤1700 px raster for speed (all filters are relative
    to image area, so results transfer), and the corners are mapped back to
    full resolution.

    Three passes, in order of strictness — the first unambiguously-clean
    geometry wins, so a good photo is never affected:
      1. CLAHE + Otsu  (the original, fastest path for well-lit sheets),
      2. adaptive threshold + morphological close      (glare / hard shadow),
      3. relaxed filters on the adaptive threshold     (folded corner, low ink).
    """
    h, w = gray.shape[:2]
    detect_scale = 1.0
    if max(h, w) > 1700:
        detect_scale = 1700.0 / max(h, w)
        small = cv2.resize(gray, None, fx=detect_scale, fy=detect_scale,
                           interpolation=cv2.INTER_AREA)
    else:
        small = gray

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    ceq = clahe.apply(small)
    blur = cv2.GaussianBlur(ceq, (5, 5), 0)
    img_area = float(small.shape[0] * small.shape[1])

    # ---- pass 1: Otsu on CLAHE (strict) -----------------------------------
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    best = _select_quad(_candidate_squares(bw, img_area))
    if best is not None:
        return best / detect_scale

    # ---- pass 2: adaptive threshold + close (glare / directional shadow) ---
    bw2 = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, 41, 9)
    # close small gaps so a glare-split anchor square reconnects into one blob
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    bw2 = cv2.morphologyEx(bw2, cv2.MORPH_CLOSE, kernel, iterations=1)
    best = _select_quad(_candidate_squares(bw2, img_area))
    if best is not None:
        return best / detect_scale

    # ---- pass 3: relaxed filters (folded corner / low contrast) -----------
    # A worn or fold-darkened corner can shrink below the strict area floor;
    # widen the windows and drop the "solid" extent requirement a little.
    best = _select_quad(_candidate_squares(bw2, img_area, relaxed=True))
    if best is not None:
        return best / detect_scale

    raise OMRReject(
        "ANCHORS_NOT_FOUND",
        "Could not find the four corner squares.",
        "Frame the whole sheet, keep it flat and evenly lit, avoid shadows "
        "over the corners. In very low light use the torch button.")


# ----------------------------------------------------------------------------
# Perspective warp
# ----------------------------------------------------------------------------
def warp_page(img: np.ndarray, corners: np.ndarray, lay: SheetLayout,
              s: AdvancedSettings) -> np.ndarray:
    scale = s.warp_width_px / lay.page_w
    dst = np.array([(ax * scale, ay * scale) for (ax, ay) in lay.anchors],
                   dtype=np.float32)
    M = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    out = cv2.warpPerspective(img, M, (int(lay.page_w * scale), int(lay.page_h * scale)),
                              flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return out


# ----------------------------------------------------------------------------
# Bubble measurement — lighting-adaptive, grid-relative
# ----------------------------------------------------------------------------
def _key(b) -> str:
    if b.kind == "option":
        return f"o{b.q}:{b.option}"
    if b.kind == "digit":
        return f"d{b.digit}:{b.value}"
    return f"p{b.bit}"



def measure_bubbles(warped_gray: np.ndarray, lay: SheetLayout,
                    s: AdvancedSettings) -> Tuple[Dict[str, float], float, int]:
    """Mean gray of the inner disc of every bubble + the printed-ink reference.

    Returns ``(gray_map, anchor_black, otsu)`` where ``anchor_black`` is the
    darkest alignment-square core — a per-photo *printed black* reference that
    follows the actual exposure of the sheet.
    """
    th, _ = cv2.threshold(warped_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = int(np.clip(th, 90, 190)) + s.dark_threshold_offset

    scale = s.warp_width_px / lay.page_w
    gray_map: Dict[str, float] = {}
    for b in lay.bubbles:
        gray_map[_key(b)] = _disc_mean(warped_gray, b.cx * scale, b.cy * scale,
                                       b.r * scale * s.inner_sample)

    # printed-ink reference: the darkest of the four solid anchor cores
    anchor_means = []
    for (ax, ay) in lay.anchors:
        m = _disc_mean(warped_gray, ax * scale, ay * scale,
                       (ANCHOR_REF_R_MM * scale))
        if m is not None:
            anchor_means.append(m)
    anchor_black = float(min(anchor_means)) if anchor_means else 60.0
    return gray_map, anchor_black, th


def _disc_mean(img: np.ndarray, cx: float, cy: float, r: float) -> Optional[float]:
    x0, x1 = int(cx - r), int(cx + r) + 1
    y0, y1 = int(cy - r), int(cy + r) + 1
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.shape[1], x1), min(img.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        return None
    roi = img[y0:y1, x0:x1].astype(np.float32)
    h, w = roi.shape
    yy, xx = np.mgrid[0:h, 0:w]
    mask = ((xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2) <= r * r
    total = int(mask.sum())
    return float(roi[mask].mean()) if total else None


def relative_map(lay: SheetLayout, gray_map: Dict[str, float],
                 anchor_black: float) -> Dict[str, float]:
    """Grid-relative fill scores, immune to exposure and local shadows.

    Every bubble is scored against its own siblings — the brightest bubble in
    the same question row / ID row is by definition *unmarked paper* under the
    same lighting, and the printed anchors define *black*.  A score of 0 means
    “as empty as its empty siblings”, 1 means “as dark as printed ink”, so a
    shadow or a bright glare band shifts the reference with it instead of
    breaking the decision.
    """
    rel: Dict[str, float] = {}
    groups: Dict[str, list] = {}
    for b in lay.bubbles:
        if b.kind == "option":
            groups.setdefault(f"q{b.q}", []).append(_key(b))
        elif b.kind == "digit":
            groups.setdefault(f"d{b.digit}", []).append(_key(b))
        else:
            groups.setdefault("p", []).append(_key(b))
    for keys in groups.values():
        grays = [gray_map[k] for k in keys if gray_map.get(k) is not None]
        if not grays:
            continue
        white = max(grays)                    # brightest sibling ≈ local paper
        span = max(white - anchor_black, 12.0)
        for k in keys:
            g = gray_map.get(k)
            rel[k] = 0.0 if g is None else float(np.clip((white - g) / span, 0.0, 1.25))
    return rel


def stroke_coverage(warped_gray: np.ndarray, lay: SheetLayout, b,
                    white_ref: float, anchor_black: float,
                    s: AdvancedSettings, dark_threshold: Optional[float] = None) -> float:
    """Largest connected dark component inside the bubble disc (CCA).

    An intentional pen/pencil stroke is one large connected blob; a printer
    smudge or a dust speck is many tiny ones.  Returns the largest component's
    area as a fraction of the sampled disc.

    ``dark_threshold`` is the per-photo Otsu cut (after ``dark_threshold_offset``)
    so the Settings → OMR "binarisation offset" fine-tune actually takes effect
    here instead of being computed and discarded.
    """
    scale = s.warp_width_px / lay.page_w
    cx, cy, r = b.cx * scale, b.cy * scale, b.r * scale * 0.95
    x0, x1 = max(0, int(cx - r)), min(warped_gray.shape[1], int(cx + r) + 1)
    y0, y1 = max(0, int(cy - r)), min(warped_gray.shape[0], int(cy + r) + 1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    roi = warped_gray[y0:y1, x0:x1]
    if dark_threshold is not None:
        t = float(dark_threshold)
    else:
        t = white_ref - 0.35 * max(white_ref - anchor_black, 12.0)
    mask = (roi < t).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    h, w = roi.shape
    yy, xx = np.mgrid[0:h, 0:w]
    disc = ((xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2) <= r * r
    disc_area = float(disc.sum())
    if disc_area <= 0:
        return 0.0
    best = 0.0
    for i in range(1, n):
        inside = float(((labels == i) & disc).sum())
        best = max(best, inside / disc_area)
    return best


# ----------------------------------------------------------------------------
# Decision model
# ----------------------------------------------------------------------------
def _decide_group(dens: List[float], t_blank: float, t_fill: float,
                  faint_upper: float, multi_ratio: float
                  ) -> Tuple[Optional[int], str, float]:
    """Return (marked_index_or_None, status, confidence).

    status ∈ {"ok", "blank", "faint", "multi"}.
    """
    order = np.argsort(dens)[::-1]
    top, second = int(order[0]), float(dens[order[1]]) if len(dens) > 1 else 0.0
    topv = float(dens[top])
    conf = float(np.clip((topv - second) / 0.45, 0, 1)) * float(np.clip(topv / 0.5, 0, 1))

    if topv < t_blank:
        return None, "blank", 0.0
    if topv < t_fill:
        return top, "faint", conf * 0.5
    others = [i for i in range(len(dens))
              if i != top and dens[i] >= max(t_fill, topv * multi_ratio)]
    if others:
        return top, "multi", conf * 0.4
    if topv < faint_upper:
        return top, "faint", conf * 0.75
    return top, "ok", conf


# ----------------------------------------------------------------------------
# Crop helper
# ----------------------------------------------------------------------------
def _crop(warped: np.ndarray, lay: SheetLayout, box_mm: Tuple[float, float, float, float],
          s: AdvancedSettings, out_dir: Path, name: str) -> str:
    scale = s.warp_width_px / lay.page_w
    x0, y0, x1, y1 = box_mm
    px = [int(x0 * scale), int(y0 * scale), int(x1 * scale), int(y1 * scale)]
    px[0], px[1] = max(0, px[0]), max(0, px[1])
    px[2] = min(warped.shape[1], px[2])
    px[3] = min(warped.shape[0], px[3])
    if px[2] <= px[0] or px[3] <= px[1]:
        return ""
    crop = warped[px[1]:px[3], px[0]:px[2]]
    h = crop.shape[0]
    if h > 0 and abs(h - 140) > 12:                   # normalise height ≈ 140 px
        f = 140.0 / h
        crop = cv2.resize(crop, (max(1, int(crop.shape[1] * f)), 140),
                          interpolation=cv2.INTER_CUBIC)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    cv2.imwrite(str(path), crop)
    return str(path)


# ----------------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------------
def grade_photo(data: bytes, lay: SheetLayout, test: TestConfig,
                s: AdvancedSettings, session_dir: Path,
                debug_dir: Optional[Path] = None) -> GradeResult:
    """Grade one photographed sheet.  Raises OMRReject for unusable photos."""
    t0 = time.perf_counter()
    img = load_image(data)
    quick_validate(img, s)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    corners = find_page_corners(gray)
    warped = warp_page(img, corners, lay, s)
    wgray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    # guard: flattened anchors must be dark
    scale = s.warp_width_px / lay.page_w
    for i, (ax, ay) in enumerate(lay.anchors):
        roi = wgray[int(ay * scale) - 8:int(ay * scale) + 8,
                    int(ax * scale) - 8:int(ax * scale) + 8]
        if roi.size and float(roi.mean()) > 140:
            raise OMRReject("WARP_FAILED", "Page alignment check failed.",
                            "Flatten the sheet and reshoot from directly above.")

    gray_map, anchor_black, dark_th = measure_bubbles(wgray, lay, s)
    rel = relative_map(lay, gray_map, anchor_black)

    if s.save_debug_warp and debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / f"warp_{int(time.time())}.png"), warped)

    # questions without a key entry are excluded from scoring — the key can
    # still be defined or completed after the sheets were printed
    keyed = [qn for qn in range(1, lay.num_questions + 1)
             if qn in test.answer_key]
    n_keyed = len(keyed)
    result = GradeResult(sheet_id=uuid.uuid4().hex[:12],
                         ts=time.strftime("%Y-%m-%d %H:%M:%S"),
                         max_score=float(sum(test.weight_for(qn) for qn in keyed)))
    crops_dir = session_dir / "review" / "crops" / result.sheet_id

    # ---------------- student ID -------------------------------------------
    if lay.student_id_digits > 0:
        id_chars: List[str] = []
        for d in range(lay.student_id_digits):
            dens = [rel.get(f"d{d}:{v}", 0.0) for v in range(10)]
            marked, status, _c = _decide_group(dens, s.t_blank, s.t_fill,
                                               s.faint_upper, s.multi_ratio)
            if status in ("ok", "faint", "multi") and marked is not None:
                id_chars.append(str(marked))
            else:
                id_chars.append("?")
            if status in ("faint", "multi", "blank"):
                y = 66.5 + d * ID_ROW_PITCH
                x1 = ID_DIGITS_X0 + 9 * ID_VALUE_PITCH + 3.0
                crop = _crop(warped, lay, (22.0, y - 2.8, x1, y + 2.8), s,
                             crops_dir, f"id_digit{d}")
                guess = str(marked) if marked is not None else None
                result.flags.append(Flag(
                    "ID" if status != "blank" else "BLANK", q=None, digit=d,
                    guess=guess,
                    message=f"Student-ID digit {d + 1}: {_status_text(status)}",
                    crop=crop))
        result.student_id = "".join(id_chars)

    # ---------------- questions --------------------------------------------
    confs: List[float] = []
    partials: List[int] = []
    answers: Dict[int, Optional[str]] = {}
    correct: Dict[int, bool] = {}

    # A per-mark connectivity fallback.  ``cov`` is the largest connected dark
    # component inside the bubble disc — a real pen/pencil stroke is one solid
    # blob; a smudge or dust is many tiny ones.  It drives two decisions:
    #    * an *ok* mark whose ink is mostly disconnected specks is really a
    #      smudge → demote to ``faint`` so it goes to review, and
    #    * a *faint* mark that is actually a solid, clearly-winning stroke (a
    #      light pen that still fills the bubble) is a confident answer → it is
    #      auto-graded instead of being sent for a human look.
    # The two gates are the net: Q19-style partial strips (cov ≈ 0.5) stay in
    # Review, while a genuinely-marks-the-bubble light stroke (cov ≥ 0.72) is
    # accepted.  Both use the Settings→OMR "binarisation offset".
    AUTO_HEAL_CONF = 0.50          # leading bubble must be a clear winner
    AUTO_HEAL_COV = 0.72           # …and mostly cover its bubble (solid stroke)

    for qn in range(1, lay.num_questions + 1):
        dens = [rel.get(f"o{qn}:{oi}", 0.0) for oi in range(lay.options_per_question)]
        marked, status, conf = _decide_group(dens, s.t_blank, s.t_fill,
                                             s.faint_upper, s.multi_ratio)

        if status in ("ok", "faint") and marked is not None:
            blk_q = lay.question_block(qn)
            if blk_q is not None:
                white_ref = max(gray_map.get(f"o{qn}:{oi}", 255.0)
                                for oi in range(lay.options_per_question))
                b_mark = next(bb for bb in lay.bubbles
                              if bb.kind == "option" and bb.q == qn
                              and bb.option == marked)
                cov = stroke_coverage(wgray, lay, b_mark, white_ref,
                                      anchor_black, s, dark_th)
                if status == "ok" and cov < 0.12:
                    status = "faint"                # disconnected specks → smudge
                elif status == "faint" and conf >= AUTO_HEAL_CONF \
                        and cov >= AUTO_HEAL_COV:
                    status = "ok"                   # light but solid → auto-grade

        # double-mark that still contains the key + partial credit policy →
        # award the fraction automatically instead of flagging
        if (status == "multi" and test.partial_multi_credit > 0
                and test.answer_key.get(qn) in
                [LETTERS[i] for i, d in enumerate(dens) if d >= s.t_fill]):
            result.score += round(test.weight_for(qn) * test.partial_multi_credit, 3)
            partials.append(qn)
            confs.append(max(conf, 0.5))
            answers[qn] = None
            correct[qn] = False
            continue

        confs.append(conf)
        letter = LETTERS[marked] if (marked is not None and status != "multi") else None
        answers[qn] = letter
        correct[qn] = bool(letter and test.answer_key.get(qn) == letter)
        if letter and correct[qn]:
            result.score += test.weight_for(qn)

        if status == "ok":
            continue
        if status == "blank" and s.auto_accept_blank:
            continue

        blk = lay.question_block(qn)
        crop = ""
        if blk is not None:
            crop = _crop(warped, lay, blk.bounds(), s, crops_dir, f"q{qn}")
        result.flags.append(Flag(
            status.upper(), q=qn,
            guess=LETTERS[marked] if marked is not None else None,
            message=f"Q{qn}: {_status_text(status)}",
            crop=crop))

    result.answers = answers
    result.correct = correct
    result.partials = partials
    result.confidence = float(np.mean(confs)) if confs else 1.0
    result.status = "review" if result.flags else "auto"
    result.duration_ms = int((time.perf_counter() - t0) * 1000)
    return result


def _status_text(status: str) -> str:
    return {
        "ok": "clear mark",
        "blank": "no bubble filled (unanswered)",
        "faint": "faint or partial mark — please verify",
        "multi": "multiple bubbles marked — invalid",
    }.get(status, status)


def flag_kind_label(kind: str) -> str:
    return {"BLANK": "Unanswered", "MULTI": "Double mark", "FAINT": "Faint mark",
            "ID": "Student ID"}.get(kind, kind)
