#!/usr/bin/env python3
"""
OPTIBubble end-to-end self-test.

1. Builds a demo test (24 questions, 4 options) and generates the sheet PDF.
2. Rasterises the PDF (PyMuPDF) and *simulates a student*: fills bubbles for
   the answer key, plus one blank, one double-mark and one faint mark.
3. Simulates a phone photo: random perspective warp, tilted paper, brightness
   gradient, sensor noise, slight blur, gray desk background, JPEG artifacts.
4. Grades the photo through the real OMR pipeline and asserts accuracy,
   flag behaviour and the < 3 s processing budget.
5. Exercises the full HTTP stack: desktop app page, settings, review resolve,
   CSV export and the mobile bridge.

Run:  python selftest.py
"""

from __future__ import annotations

import io
import random
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from optibubble.config import AdvancedSettings, TestConfig
from optibubble.hub import Hub
from optibubble.layout import SheetLayout
from optibubble.omr_engine import OMRReject, grade_photo
from optibubble.sheet_generator import generate_sheet_pdf

PASS, FAIL = "✔", "✕"
results: list = []


def check(name: str, cond: bool, extra: str = ""):
    results.append((name, cond, extra))
    print(f" {PASS if cond else FAIL} {name}" + (f"   [{extra}]" if extra else ""))


# --------------------------------------------------------------------------
def render_pdf(pdf_path: Path, dpi: int = 160) -> np.ndarray:
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    pix = doc[0].get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img


def fill_bubble(img: np.ndarray, mm2px: float, cx, cy, r, strength="pen", rng=None):
    """Simulate a hand-filled bubble (hatch strokes inside the inner disc)."""
    rng = rng or random
    C = (int(cx * mm2px), int(cy * mm2px))
    R = int(r * mm2px * rng.uniform(0.80, 0.92))
    if strength == "faint":
        # realistic partial mark: a vertical strip covers ~60% of the bubble
        R2 = int(r * mm2px * 0.85)
        cx0, cy0 = C
        disc = np.zeros(img.shape[:2], np.uint8)
        cv2.circle(disc, C, R2, 255, -1)
        strip = np.zeros(img.shape[:2], np.uint8)
        cv2.rectangle(strip, (cx0 - int(R2 * 0.30), cy0 - int(R2 * 0.95)),
                      (cx0 + int(R2 * 0.30), cy0 + int(R2 * 0.95)), 255, -1)
        mask = (disc > 0) & (strip > 0)
        img[mask] = (rng.randint(30, 50),) * 3
        return
    shade = {"pen": rng.randint(20, 55), "pencil": rng.randint(60, 95)}[strength]
    overlay = img.copy()
    cv2.circle(overlay, C, R, (shade,) * 3, -1)
    if strength == "pen":
        for _ in range(rng.randint(2, 4)):
            a = rng.uniform(0, 2 * np.pi)
            d = rng.uniform(0.15, 0.55) * R
            p1 = (int(C[0] + np.cos(a) * d), int(C[1] + np.sin(a) * d))
            a2 = a + np.pi + rng.uniform(-0.6, 0.6)
            p2 = (int(C[0] + np.cos(a2) * d), int(C[1] + np.sin(a2) * d))
            cv2.line(overlay, p1, p2, (shade,), max(2, int(R * 0.35)))
        cv2.addWeighted(overlay, 0.92, img, 0.08, 0, dst=img)
        return
    cv2.addWeighted(overlay, 0.92, img, 0.08, 0, dst=img)


def simulate_photo(flat: np.ndarray, lay: SheetLayout, seed: int = 7) -> np.ndarray:
    """Warp the flat sheet into a realistic phone photo."""
    rng = np.random.default_rng(seed)
    h, w = flat.shape[:2]
    PH, PW = int(h * 1.35), int(w * 1.35)
    jx, jy = PW * 0.035, PH * 0.03
    pts = np.array([
        [PW * 0.10 + rng.uniform(-jx, jx), PH * 0.06 + rng.uniform(-jy, jy)],
        [PW * 0.94 + rng.uniform(-jx, jx), PH * 0.05 + rng.uniform(-jy, jy)],
        [PW * 0.95 + rng.uniform(-jx, jx), PH * 0.96 + rng.uniform(-jy, jy)],
        [PW * 0.09 + rng.uniform(-jx, jx), PH * 0.97 + rng.uniform(-jy, jy)],
    ], dtype=np.float32)
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, pts)
    warped = cv2.warpPerspective(flat, M, (PW, PH), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=(92, 96, 104))
    shadow = np.ones((PH, PW), np.float32)
    for x in range(PW):
        shadow[:, x] = 1.0 - 0.22 * (x / PW)
    for y in range(PH):
        shadow[y, :] *= 1.0 - 0.10 * (y / PH)
    warped = np.clip(warped.astype(np.float32) * shadow[..., None], 0, 255)
    photo = warped.astype(np.uint8)
    noise = rng.normal(0, 6.5, photo.shape).astype(np.float32)
    photo = np.clip(photo.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    photo = cv2.GaussianBlur(photo, (0, 0), 0.9)
    ok, buf = cv2.imencode(".jpg", photo, [cv2.IMWRITE_JPEG_QUALITY, 88])
    photo = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    scale = 2048 / PW
    photo = cv2.resize(photo, (int(PW * scale), int(PH * scale)),
                       interpolation=cv2.INTER_AREA)
    return photo


def encode_jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes()


# --------------------------------------------------------------------------
def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="optibubble_selftest_"))
    print(f"\nOPTIBubble self-test — workspace: {tmp}\n")

    # ---- build test ------------------------------------------------------
    test = TestConfig(title="Physics Midterm", subject="Physics",
                      num_questions=24, options_per_question=4,
                      student_id_digits=7, page_size="a4")
    test.ensure_ids()
    test.randomize_key()
    pdf, lay = generate_sheet_pdf(test, tmp / "sheet.pdf")

    settings = AdvancedSettings()
    flat = render_pdf(pdf)
    mm2px = flat.shape[1] / lay.page_w          # pixels per millimetre

    check("PDF generated + rasterised", flat.shape[0] > 1000, f"{flat.shape[1]}×{flat.shape[0]}")
    check("Sheet layout has all bubbles",
          len(lay.bubbles) == 24 * 4 + 7 * 10, f"{len(lay.bubbles)} bubbles")

    # ---- simulate student answers ---------------------------------------
    key = test.answer_key
    marked = dict(key)
    marked[7] = None          # blank
    marked[12] = key[12]      # will become double-mark
    marked[19] = key[19]      # will become faint
    student_id = "2041986"

    for qn, letter in marked.items():
        if letter is None:
            continue
        blk = lay.question_block(qn)
        oi = "ABCD".index(letter)
        b = [bb for bb in lay.bubbles if bb.kind == "option" and bb.q == qn][oi]
        strength = "faint" if qn == 19 else "pen"
        fill_bubble(flat, mm2px, b.cx, b.cy, b.r, strength)
    b2 = [bb for bb in lay.bubbles if bb.kind == "option" and bb.q == 12]
    key12_idx = "ABCD".index(key[12])
    other = (key12_idx + 1) % 4
    fill_bubble(flat, mm2px, b2[other].cx, b2[other].cy, b2[other].r, "pen")
    for d, ch in enumerate(student_id):
        bb = lay.digit_bubbles(d)[int(ch)]
        fill_bubble(flat, mm2px, bb.cx, bb.cy, bb.r, "pen")

    # ---- photo → grade ---------------------------------------------------
    for seed in (7, 42, 123):
        photo = simulate_photo(flat, lay, seed=seed)
        data = encode_jpeg(photo)
        t0 = time.perf_counter()
        res = grade_photo(data, lay, test, settings, tmp)
        dt = time.perf_counter() - t0

        expected_score = sum(1 for q, a in marked.items()
                             if a and q not in (7, 12) and key[q] == a)
        kinds = {f.kind for f in res.flags}
        ok_seed = (res.student_id == student_id
                   and res.score == expected_score
                   and res.status == "review"
                   and {"BLANK", "MULTI", "FAINT"} <= kinds
                   and dt < 3.0)
        check(f"photo seed {seed}: graded", ok_seed,
              f"score {res.score}/{res.max_score} (exp {expected_score}) · "
              f"ID {res.student_id} · flags {sorted(kinds)} · {dt*1000:.0f} ms")

    # ---- rejection cases --------------------------------------------------
    try:
        grade_photo(encode_jpeg(np.full((400, 300, 3), 255, np.uint8)),
                    lay, test, settings, tmp)
        check("low-res photo rejected", False)
    except OMRReject as e:
        check("low-res photo rejected", e.code == "LOW_RES", e.code)

    white = np.full((2400, 1900, 3), 232, np.uint8)
    cv2.rectangle(white, (100, 100), (300, 300), (0, 0, 0), -1)   # decoy blob
    try:
        grade_photo(encode_jpeg(white), lay, test, settings, tmp)
        check("anchor-less photo rejected", False)
    except OMRReject as e:
        check("anchor-less photo rejected", e.code == "ANCHORS_NOT_FOUND", e.code)

    # ---- full stack: hub + flask -----------------------------------------
    from optibubble.server import create_app
    hub = Hub(data_dir=tmp / "data")
    hub.create_test(TestConfig(
        title="Stack Test", subject="CS", num_questions=24, options_per_question=4,
        answer_key=dict(key), student_id_digits=7, page_size="a4",
        test_id=test.test_id, session_token=test.session_token))
    photo = simulate_photo(flat, lay, seed=5)
    client = create_app(hub).test_client()

    r = client.get("/")
    check("desktop app page served", r.status_code == 200 and b"OPTIBubble" in r.data)
    r = client.get("/api/state")
    check("state snapshot", r.status_code == 200 and r.get_json()["test"] is not None)
    r = client.get("/api/settings")
    check("settings read", r.status_code == 200 and "t_fill" in r.get_json())
    r = client.post("/api/settings", json={"t_fill": 0.4})
    check("settings write", r.status_code == 200 and r.get_json()["t_fill"] == 0.4)
    r = client.get(f"/scan/{test.session_token}")
    check("mobile page served", r.status_code == 200 and b"OPTIBubble" in r.data)
    r = client.get(f"/api/info/{test.session_token}")
    check("info endpoint", r.status_code == 200 and r.get_json()["questions"] == 24)
    r = client.get("/api/preview.png")
    check("sheet preview render", r.status_code == 200
          and r.data[:4] == b"\x89PNG")

    r = client.post(f"/api/upload/{test.session_token}",
                    data={"photo": (io.BytesIO(encode_jpeg(photo)), "s.jpg")},
                    content_type="multipart/form-data")
    rid = r.get_json().get("receipt")
    check("upload accepted", r.status_code == 200 and rid, str(r.get_json()))
    outcome = {}
    for _ in range(60):
        outcome = client.get(f"/api/receipt/{rid}").get_json()
        if outcome.get("status") in ("done", "error"):
            break
        time.sleep(0.1)
    check("receipt graded", outcome.get("status") == "done",
          str(outcome.get("result") or outcome.get("error")))
    check("flagged sheet queued for review",
          len(client.get("/api/review").get_json()) == 1)

    reviews = client.get("/api/review").get_json()
    crop_url = next((f["crop"] for f in reviews[0]["flags"] if f["crop"]), "")
    if crop_url:
        from urllib.parse import unquote
        r2 = client.get(crop_url)
        check("crop evidence image served", r2.status_code == 200)

    sid = outcome["result"]["sheet_id"]
    r = client.post("/api/review/resolve",
                    json={"sheet_id": sid, "answers": {"7": "C"},
                          "student_id": "2041986"})
    check("review resolved via API", r.status_code == 200)
    csv_path = hub.storage.test_root(hub.test) / "results.csv"
    csv_text = csv_path.read_text()
    check("CSV written + schema", "2041986" in csv_text and "Verified" in csv_text
          and "Detailed_Answers_JSON" in csv_text)
    check("master CSV written", (hub.data_dir / "master_results.csv").exists())
    r = client.get("/api/results/export.csv")
    check("CSV export download", r.status_code == 200 and b"Student_ID" in r.data)
    check("QR endpoint", client.get("/api/qr.png").status_code == 200)

    # layout stress: 100 & 102 questions, letter paper
    for label, (nq, k, page) in {"100Q/5opt": (100, 5, "a4"),
                                 "88Q letter": (88, 4, "letter")}.items():
        t2 = TestConfig(title=label, num_questions=nq, options_per_question=k,
                        student_id_digits=7, page_size=page)
        t2.ensure_ids(); t2.randomize_key()
        pdf2, lay2 = generate_sheet_pdf(t2, tmp / f"s{nq}_{k}_{page}.pdf")
        flat2 = render_pdf(pdf2)
        mm2 = flat2.shape[1] / lay2.page_w
        for qn, letter in t2.answer_key.items():
            idx = "ABCDE"[:k].index(letter)
            b = [bb for bb in lay2.bubbles if bb.kind == "option" and bb.q == qn][idx]
            fill_bubble(flat2, mm2, b.cx, b.cy, b.r, "pen")
        for d, ch in enumerate("7315902"):
            bb = lay2.digit_bubbles(d)[int(ch)]
            fill_bubble(flat2, mm2, bb.cx, bb.cy, bb.r, "pen")
        res2 = grade_photo(encode_jpeg(simulate_photo(flat2, lay2, seed=11)),
                           lay2, t2, settings, tmp)
        check(f"layout {label}", res2.score == nq and res2.student_id == "7315902"
              and res2.status == "auto",
              f"{res2.score}/{res2.max_score} · ID {res2.student_id} · "
              f"{res2.duration_ms} ms")

    # ---- sheet designer: editable header + validation ---------------------
    from optibubble.layout import SheetLayout, LayoutError
    t3 = TestConfig(title="Designer Test", num_questions=40, options_per_question=4,
                    student_id_digits=10)          # 10 digits push the grid down
    t3.ensure_ids()
    lay3 = SheetLayout.build(t3)
    check("10-digit ID pushes questions below the strip",
          lay3.questions_top > 104 and not lay3.warnings is None,
          f"questions_top={lay3.questions_top:.1f}")

    t4 = TestConfig(title="Designer Test 2", num_questions=10,
                    sheet_instructions="Custom instructions for the header test.",
                    header_font_scale=1.4, logo_position="right")
    t4.ensure_ids()
    pdf4, _ = generate_sheet_pdf(t4, tmp / "designer.pdf")
    check("custom header renders (instructions + 140% + logo right)",
          pdf4.exists() and pdf4.stat().st_size > 4000)

    try:
        generate_sheet_pdf(TestConfig(title="Bad", num_questions=10,
                                      sheet_instructions="W" * 240,
                                      header_font_scale=1.4), tmp / "bad.pdf")
        t4.ensure_ids()
        check("impossible header rejected", False)
    except ValueError as e:
        check("impossible header rejected", "does not fit" in str(e), str(e)[:40])

    r = client.post("/api/tests", content_type="application/json", json={
        "title": "API Sheet Design", "num_questions": 12, "options_per_question": 4,
        "student_id_digits": 7, "page_size": "a4",
        "sheet_instructions": "Answer all questions in blue or black pen.",
        "header_font_scale": 1.2, "logo_position": "right",
        "answer_key": {str(i): "ABCD"[i % 4] for i in range(1, 13)}})
    j = r.get_json()
    check("API accepts sheet-design fields", r.status_code == 200 and j.get("ok"),
          str(j.get("errors", ""))[:60])

    print()
    bad = [n for n, ok, _ in results if not ok]
    print(f"{len(results) - len(bad)}/{len(results)} checks passed")
    if bad:
        print("FAILED:", bad)
        return 1
    print("ALL GREEN — engine, generator, server, web app and export verified.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
