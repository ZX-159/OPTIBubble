"""Build docs figures: pipeline demo + sheet sample + phone-photo sample."""
import sys, tempfile
from pathlib import Path
import numpy as np, cv2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selftest import render_pdf, fill_bubble, simulate_photo, encode_jpeg
from optibubble.config import TestConfig, AdvancedSettings
from optibubble.sheet_generator import generate_sheet_pdf
from optibubble.omr_engine import (find_page_corners, warp_page, measure_bubbles,
                                   relative_map, _decide_group)

GREEN, RED, AMBER, WHITE_B = (34, 197, 94), (239, 68, 68), (245, 158, 11), (255, 255, 255)

# ---------- 100-question sheet sample ----------
t100 = TestConfig(title="Mathematics Final — Form B", subject="Mathematics",
                  num_questions=100, options_per_question=5, student_id_digits=7)
t100.ensure_ids(); t100.randomize_key()
tmp = Path(tempfile.mkdtemp(prefix="fig_"))
pdf100, lay100 = generate_sheet_pdf(t100, tmp / "s100.pdf")
flat100 = render_pdf(pdf100, dpi=140)
mm2px = flat100.shape[1] / lay100.page_w
for qn, letter in t100.answer_key.items():
    idx = "ABCDE".index(letter)
    b = [bb for bb in lay100.bubbles if bb.kind == "option" and bb.q == qn][idx]
    fill_bubble(flat100, mm2px, b.cx, b.cy, b.r, "pen")
for d, ch in enumerate("5120477"):
    bb = lay100.digit_bubbles(d)[int(ch)]
    fill_bubble(flat100, mm2px, bb.cx, bb.cy, bb.r, "pen")
cv2.imwrite(str(Path(__file__).parent / "sheet-sample.png"), flat100,
            [cv2.IMWRITE_PNG_COMPRESSION, 8])

# ---------- pipeline figure ----------
t = TestConfig(title="Pipeline Demo", subject="Math", num_questions=24,
               options_per_question=4, student_id_digits=7)
t.ensure_ids(); t.randomize_key()
pdf, lay = generate_sheet_pdf(t, tmp / "s.pdf")
flat = render_pdf(pdf)
mm2px = flat.shape[1] / lay.page_w

for qn, letter in t.answer_key.items():
    if qn == 5:
        continue
    if qn == 9:
        bs = [bb for bb in lay.bubbles if bb.kind == "option" and bb.q == qn]
        fill_bubble(flat, mm2px, bs[1].cx, bs[1].cy, bs[1].r, "pen")
        fill_bubble(flat, mm2px, bs[3].cx, bs[3].cy, bs[3].r, "pen")
        continue
    strength = "faint" if qn == 17 else "pen"
    idx = "ABCD".index(letter)
    b = [bb for bb in lay.bubbles if bb.kind == "option" and bb.q == qn][idx]
    fill_bubble(flat, mm2px, b.cx, b.cy, b.r, strength)
for d, ch in enumerate("3141592"):
    bb = lay.digit_bubbles(d)[int(ch)]
    fill_bubble(flat, mm2px, bb.cx, bb.cy, bb.r, "pen")

photo = simulate_photo(flat, lay, seed=99)
S = AdvancedSettings()

p1 = photo.copy()
gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
corners = find_page_corners(gray)
pts = np.vstack([corners, corners[:1]]).astype(int)
cv2.polylines(p1, [pts], False, GREEN, 8, cv2.LINE_AA)
for c in corners.astype(int):
    cv2.circle(p1, tuple(c), 16, (96, 165, 250), 8)
cv2.putText(p1, "1  detect corner squares", (30, 60), cv2.FONT_HERSHEY_SIMPLEX,
            1.5, WHITE_B, 4, cv2.LINE_AA)

warp = warp_page(photo, corners, lay, S)
gm, black, _th = measure_bubbles(cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY), lay, S)
ratios = relative_map(lay, gm, black)
scale = S.warp_width_px / lay.page_w
p3 = warp.copy()
for qn in range(1, lay.num_questions + 1):
    dens = [ratios.get(f"o{qn}:{oi}", 0.0) for oi in range(4)]
    marked, status, conf = _decide_group(dens, S.t_blank, S.t_fill, S.faint_upper, S.multi_ratio)
    color = {"ok": GREEN, "blank": (148, 163, 184), "faint": AMBER, "multi": RED}[status]
    for oi, b in enumerate([bb for bb in lay.bubbles if bb.kind == "option" and bb.q == qn]):
        c = (int(b.cx * scale), int(b.cy * scale))
        r = int(b.r * scale)
        if status == "ok" and oi == marked:
            cv2.circle(p3, c, r + 4, color, 4, cv2.LINE_AA)
        else:
            cv2.circle(p3, c, r + 4, color, 3, cv2.LINE_AA)
    blk = lay.question_block(qn)
    if status != "ok":
        cv2.putText(p3, f"Q{qn}:{status}", (int((blk.label_cx - 8) * scale),
                    int(blk.y * scale) + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

p2 = warp.copy()
cv2.putText(p2, "2  perspective-corrected", (30, 60), cv2.FONT_HERSHEY_SIMPLEX,
            1.4, WHITE_B, 4, cv2.LINE_AA)
cv2.putText(p3, "3  per-bubble dark density -> grade", (30, 60),
            cv2.FONT_HERSHEY_SIMPLEX, 1.4, WHITE_B, 4, cv2.LINE_AA)

H = 1100
def rs(im):
    return cv2.resize(im, (int(im.shape[1] * H / im.shape[0]), H))
sep = np.full((H, 8, 3), 30, np.uint8)
combo = np.hstack([rs(p1), sep, rs(p2), sep, rs(p3)])
cv2.imwrite(str(Path(__file__).parent / "pipeline.png"), combo,
            [cv2.IMWRITE_PNG_COMPRESSION, 9])
cv2.imwrite(str(Path(__file__).parent / "photo-sample.jpg"), photo,
            [cv2.IMWRITE_JPEG_QUALITY, 82])
print("figures saved:", Path(__file__).parent)
