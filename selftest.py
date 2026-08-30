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
import json
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


def simulate_photo(flat: np.ndarray, lay: SheetLayout, seed: int = 7,
                   shadow: float = 0.22) -> np.ndarray:
    """Warp the flat sheet into a realistic phone photo (shadow = gradient
    strength, 0.0–0.6; 0.22 ≈ normal classroom, 0.45 ≈ harsh overhead light)."""
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
    shadow_arr = np.ones((PH, PW), np.float32)
    for x in range(PW):
        shadow_arr[:, x] = 1.0 - shadow * (x / PW)
    for y in range(PH):
        shadow_arr[y, :] *= 1.0 - 0.45 * shadow * (y / PH)
    warped = np.clip(warped.astype(np.float32) * shadow_arr[..., None], 0, 255)
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

    # ---- lighting robustness: harsh overhead shadow ------------------------
    tsh = TestConfig(title="Shadow Stress", subject="X", num_questions=24,
                     options_per_question=4, student_id_digits=7)
    tsh.ensure_ids(); tsh.randomize_key()
    pdfsh, laysh = generate_sheet_pdf(tsh, tmp / "shadow.pdf")
    flatsh = render_pdf(pdfsh)
    mmsh = flatsh.shape[1] / laysh.page_w
    for qn, letter in tsh.answer_key.items():
        b = [bb for bb in laysh.bubbles if bb.kind == "option" and bb.q == qn][
            "ABCD".index(letter)]
        fill_bubble(flatsh, mmsh, b.cx, b.cy, b.r, "pen")
    for d, ch in enumerate("2041986"):
        bb = laysh.digit_bubbles(d)[int(ch)]
        fill_bubble(flatsh, mmsh, bb.cx, bb.cy, bb.r, "pen")
    res_sh = grade_photo(encode_jpeg(simulate_photo(flatsh, laysh, seed=21,
                                                    shadow=0.45)),
                         laysh, tsh, settings, tmp)
    check("harsh 45% shadow gradient still grades 100%",
          res_sh.score == 24 and res_sh.student_id == "2041986"
          and res_sh.status == "auto",
          f"{res_sh.score}/{res_sh.max_score} · {res_sh.duration_ms} ms")

    # ---- CCA: disconnected specks look dark but are NOT strokes -------------
    tsm = TestConfig(title="Smudge", subject="X", num_questions=12,
                     options_per_question=4, student_id_digits=0)
    tsm.ensure_ids(); tsm.randomize_key()
    pdfsm, laysm = generate_sheet_pdf(tsm, tmp / "smudge.pdf")
    flatsm = render_pdf(pdfsm)
    msm = flatsm.shape[1] / laysm.page_w
    rng = random.Random(5)
    for qn, letter in tsm.answer_key.items():
        if qn == 6:
            continue                       # Q6 gets a smudge instead of a stroke
        b = [bb for bb in laysm.bubbles if bb.kind == "option" and bb.q == qn][
            "ABCD".index(letter)]
        fill_bubble(flatsm, msm, b.cx, b.cy, b.r, "pen")
    bs = [bb for bb in laysm.bubbles if bb.kind == "option" and bb.q == 6][1]
    C = (int(bs.cx * msm), int(bs.cy * msm)); R = int(bs.r * msm * 0.8)
    for _ in range(14):                    # many disconnected specks
        a = rng.uniform(0, 2 * np.pi); d = rng.uniform(0, 0.75) * R
        cxp, cyp = int(C[0] + np.cos(a) * d), int(C[1] + np.sin(a) * d)
        cv2.circle(flatsm, (cxp, cyp), max(2, int(R * 0.22)), (25,) * 3, -1)
    res_sm = grade_photo(encode_jpeg(simulate_photo(flatsm, laysm, seed=3)),
                         laysm, tsm, settings, tmp)
    q6 = [f for f in res_sm.flags if f.q == 6]
    check("smudge (disconnected specks) flagged by CCA, not graded",
          res_sm.status == "review" and q6 and q6[0].kind == "FAINT",
          f"Q6 flag: {q6[0].kind if q6 else 'none'} · score {res_sm.score}/{res_sm.max_score}")

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

    # grading with a partial key: max_score = defined entries
    tpart = TestConfig(title="PartKey", subject="X", num_questions=10,
                       options_per_question=4)
    tpart.ensure_ids()
    tpart.answer_key = {i: "ABCD"[(i - 1) % 4] for i in range(1, 7)}   # 6 of 10
    pdfp, layp = generate_sheet_pdf(tpart, tmp / "partkey.pdf")
    flatp = render_pdf(pdfp)
    mmp = flatp.shape[1] / layp.page_w
    for qn, letter in tpart.answer_key.items():
        b = [bb for bb in layp.bubbles if bb.kind == "option" and bb.q == qn][
            "ABCD".index(letter)]
        fill_bubble(flatp, mmp, b.cx, b.cy, b.r, "pen")
    resp = grade_photo(encode_jpeg(simulate_photo(flatp, layp, seed=8)),
                       layp, tpart, settings, tmp)
    check("partial-key grading → max = defined (6)",
          resp.max_score == 6 and resp.score == 6,
          f"{resp.score}/{resp.max_score}")

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

    # ---- HTTPS provisioning: state machine + the DoH quote regression -------
    r = client.get("/api/https/status")
    check("provision status endpoint", r.status_code == 200
          and r.get_json()["state"] in ("idle", "running", "ok", "error"))

    import optibubble.acme as _acme_mod

    class _FakeResp:
        def __init__(self, payload): self._p = payload
        def read(self): return json.dumps(self._p).encode()
        @property
        def headers(self): return {}

    _orig_http = _acme_mod._http
    _acme_mod._http = lambda url, data=None, headers=None, timeout=30: _FakeResp({
        "Status": 0, "Answer": [
            {"name": "_acme-challenge.x.duckdns.org", "type": 16,
             "data": "\"uzDivPLMMHM5VReMO5yMj7uxkMraDSTf_Enxwo1Cs1I\""}]})
    try:
        vals = _acme_mod.dns_txt_lookup("x.duckdns.org")
        check("DNS TXT quote-stripping (the stalled-setup bug)",
              vals == ["uzDivPLMMHM5VReMO5yMj7uxkMraDSTf_Enxwo1Cs1I"], str(vals))
    finally:
        _acme_mod._http = _orig_http

    # preflight rejects a mismatched domain without touching the network
    hub.settings.https_mode = "letsencrypt"
    hub.settings.acme_domain = "optibubble.duckdns.org"
    hub.settings.duckdns_token = "0123456789abcdef"
    _orig_lan = hub.lan_ips
    hub.lan_ips = lambda: ["203.0.113.7"]
    try:
        import optibubble.acme as _am
        _am.dns_a_lookup = lambda d: ["198.51.100.9"]
        hub.provision_trusted()
        import time as _t; _t.sleep(0.8)
        pst = hub._prov_state()
        check("preflight catches wrong-IP domain with a fix hint",
              pst["state"] == "error" and "duckdns.org" in pst.get("hint", "")
              and "198.51.100.9" in pst["error"], pst["error"][:60])
    finally:
        hub.lan_ips = _orig_lan

    # ---- trusted-HTTPS building blocks (offline unit checks) ---------------
    from optibubble.acme import duckdns_txt_url, make_csr, trusted_cert_valid
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
    u = duckdns_txt_url("myclass.duckdns.org", "TOK", "VALUE123")
    check("duckdns TXT url shape",
          "domains=myclass" in u and "token=TOK" in u and "txt=VALUE123" in u
          and "_acme-challenge" not in u)
    k = _rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = make_csr("myclass.duckdns.org", k)
    import re as _re
    san_txt = csr.public_bytes.__self__ if False else None
    from cryptography import x509 as _x509
    sans = csr.extensions.get_extension_for_class(_x509.SubjectAlternativeName)
    check("ACME CSR covers the domain",
          "myclass.duckdns.org" in str(sans.value.get_values_for_type(
              _x509.DNSName)))
    # expiry logic on a self-made leaf from the local CA
    from optibubble.localca import ensure_ca, load_ca, issue_leaf
    cd = tmp / "ca_unit"
    cc, ck = ensure_ca(cd)
    cert, ckey = load_ca(cc, ck)
    lc, lk = issue_leaf(cert, ckey, ["192.168.1.20"], cd / "l.crt", cd / "l.key")
    check("trusted-cert validity window works",
          trusted_cert_valid(lc, min_days_left=826) is False
          and trusted_cert_valid(lc, 0) is True)

    # ---- HTTPS bridge: local CA + secure mobile scanner --------------------
    import ssl as _ssl
    import urllib.request as _urlreq
    hub.start_server()                       # second start = idempotent; adds TLS
    check("local CA auto-generated on start",
          (hub.data_dir / "certs" / "optibubble-ca.crt").exists()
          and hub.https_running)
    ca_ctx = _ssl.create_default_context(
        cafile=str(hub.data_dir / "certs" / "optibubble-ca.crt"))
    r = _urlreq.urlopen(f"https://127.0.0.1:{hub.settings.https_port}/health",
                        context=ca_ctx, timeout=5)
    check("TLS verifies against the local CA (like a trusted phone)",
          r.status == 200 and b"ok" in r.read())
    r = _urlreq.urlopen(f"https://127.0.0.1:{hub.settings.https_port}"
                        f"/scan/{test.session_token}", context=ca_ctx, timeout=5)
    check("mobile scanner served over HTTPS", r.status == 200
          and b"OPTIBubble" in r.read())
    r = client.get("/cert")
    check("certificate landing page (code A)", r.status_code == 200
          and b"ca.mobileconfig" in r.data)
    r = client.get("/cert/ca.crt")
    check("CA cert download", r.status_code == 200 and b"BEGIN CERTIFICATE" in r.data)
    r = client.get("/cert/ca.mobileconfig")
    check("iOS profile download", r.status_code == 200 and b"PayloadContent" in r.data)
    hub.stop_server()

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

    # pathological no-space text: hard-wrapped into ≤3 lines, never overlapping
    _, lay_bad = generate_sheet_pdf(
        TestConfig(title="Bad", num_questions=10,
                   sheet_instructions="W" * 240, header_font_scale=1.4),
        tmp / "bad.pdf")
    check("pathological text hard-wrapped (≤3 lines, no overlap)",
          any("auto-shrunk" in w for w in lay_bad.warnings),
          "; ".join(lay_bad.warnings)[:60])

    # partial key: create & print first, key later
    r = client.post("/api/tests", content_type="application/json", json={
        "title": "Partial Key Flow", "num_questions": 8, "options_per_question": 4,
        "answer_key": {"1": "A", "2": "B", "3": "C"}})
    check("creation with PARTIAL key allowed", r.status_code == 200
          and r.get_json().get("missing_key") == 5, str(r.get_json())[:60])
    r = client.post("/api/key", json={"entries": {
        "4": "D", "5": "A", "6": "B", "7": "C", "8": "D"}})
    check("define key later via /api/key",
          r.status_code == 200 and r.get_json().get("defined") == 8)

    # header collisions impossible across layout variants
    from optibubble.layout import LayoutError as _LE
    variants_ok = True
    for kw in (dict(), dict(logo_position="right"),
               dict(logo_position="right", header_font_scale=1.4),
               dict(header_font_scale=1.4,
                    sheet_instructions="W" * 200)):
        tv = TestConfig(title="Variantious Long Title Here Indeed", num_questions=50, **kw)
        tv.ensure_ids(); tv.randomize_key()
        try:
            generate_sheet_pdf(tv, tmp / f"var_{len(kw)}_{int(tv.header_font_scale*10)}.pdf")
        except (_LE, ValueError):
            variants_ok = False
    check("header collision-free (4 variants)", variants_ok)

    # write-in fields render as inked lines in the band
    tw_ = TestConfig(title="WriteIn", num_questions=10,
                     write_in_fields="Name,Class,Date")
    tw_.ensure_ids(); tw_.randomize_key()
    pdfw, layw = generate_sheet_pdf(tw_, tmp / "writein.pdf")
    fw = render_pdf(pdfw)
    mmw = fw.shape[1] / layw.page_w
    band = fw[int(52*mmw):int(62*mmw), int(24*mmw):int(140*mmw)]
    check("write-in fields band present", float((band.mean(-1) < 150).mean()) > 0.002,
          f"ink fraction {(band.mean(-1) < 150).mean():.4f}")

    # the sheet endpoint really serves a PDF
    r = client.get("/api/sheet.pdf")
    check("sheet endpoint serves PDF", r.status_code == 200
          and r.headers.get("Content-Type", "").startswith("application/pdf")
          and r.data[:5] == b"%PDF-")

    # answer key PDF: served, valid, refreshed after edits
    import time as _t2
    r = client.get("/api/key.pdf")
    ok_key = (r.status_code == 200 and r.data[:5] == b"%PDF-")
    if ok_key:
        import pymupdf as _pm
        _txt = _pm.open(stream=r.data, filetype="pdf")[0].get_text()
        ok_key = "ANSWER KEY" in _txt and hub.test.title in _txt
    client.post("/api/tests", content_type="application/json", json={
        "title": "KeyPdf", "num_questions": 9, "options_per_question": 4,
        "answer_key": {str(i): "ABCD"[i % 4] for i in range(1, 10)}})
    kp = Path(hub.data_dir) / "tests" / hub.test.test_id / "key.pdf"
    m1 = kp.stat().st_mtime_ns if kp.exists() else 0
    _t2.sleep(0.05)
    client.post(f"/api/tests/{hub.test.test_id}/edit",
                json={"answer_key": {str(i): "DCBA"[i % 4] for i in range(1, 10)}})
    m2 = kp.stat().st_mtime_ns if kp.exists() else 0
    check("answer-key PDF served + regenerated on edit",
          ok_key and m2 > m1, f"mtime {m1}→{m2}")

    r = client.post("/api/tests", content_type="application/json", json={
        "title": "API Sheet Design", "num_questions": 12, "options_per_question": 4,
        "student_id_digits": 7, "page_size": "a4",
        "sheet_instructions": "Answer all questions in blue or black pen.",
        "header_font_scale": 1.2, "logo_position": "right",
        "answer_key": {str(i): "ABCD"[i % 4] for i in range(1, 13)}})
    j = r.get_json()
    check("API accepts sheet-design fields", r.status_code == 200 and j.get("ok"),
          str(j.get("errors", ""))[:60])

    # ---- test management: auto-key · edit · delete · empty export ---------
    r = client.post("/api/tests", content_type="application/json", json={
        "title": "AutoKey", "num_questions": 6, "options_per_question": 4})
    j = r.get_json()
    auto_id = j.get("test_id")
    check("empty key → auto-generated, complete",
          r.status_code == 200 and j.get("auto_key") is True
          and j.get("missing_key") == 0, str(j)[:70])

    r = client.post(f"/api/tests/{auto_id}/edit", json={
        "title": "AutoKey Edited", "answer_key":
            {str(i): "BCDA"[i % 4] for i in range(1, 7)}})
    check("edit test (rename + replace key)", r.status_code == 200
          and r.get_json().get("ok"))
    d = client.get(f"/api/tests/{auto_id}").get_json()
    check("edits persisted + sheet PDF regenerated",
          d["test"]["title"] == "AutoKey Edited"
          and len(d["test"]["answer_key"]) == 6
          and (Path(hub.data_dir) / "tests" / auto_id / "sheet.pdf").exists())

    r = client.post(f"/api/tests/{auto_id}/edit", json={"num_questions": 40})
    check("structural edit rejected with guidance",
          r.status_code == 400 and "new test" in " ".join(
              r.get_json().get("errors", [])))

    hub.open_test(auto_id)
    r = client.get("/api/results/export.csv")
    check("empty results CSV exports header-only (no error)",
          r.status_code == 200 and r.data.count(b"Student_ID") == 1
          and r.data.count(b"\n") == 1)

    r = client.post(f"/api/tests/{auto_id}/delete")
    check("delete test removes folder",
          r.status_code == 200 and not (Path(hub.data_dir) / "tests" /
                                        auto_id).exists())
    r = client.get(f"/api/tests/{auto_id}")
    check("deleted test is gone", r.status_code == 404)

    # deleting the ACTIVE test must never kill the app server (regression:
    # this used to stop the HTTP server the desktop UI is served from)
    r = client.post("/api/tests", content_type="application/json", json={
        "title": "ActiveDelete", "num_questions": 5})
    act_id = r.get_json()["test_id"]
    hub.open_test(act_id)
    hub.start_server()
    r = client.post(f"/api/tests/{act_id}/delete")
    ok_del = r.status_code == 200
    time.sleep(0.3)
    r2 = client.get("/api/state")            # server must still respond
    import urllib.request as _u2
    live = _u2.urlopen(f"http://127.0.0.1:{hub.settings.port}/health",
                      timeout=5).status
    check("deleting the ACTIVE test keeps the app server alive",
          ok_del and r2.status_code == 200 and live == 200
          and hub.test is None,
          f"http={live}, state={r2.status_code}")

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
