"""Seed a demo session through the REAL pipeline, then screenshot the web UI."""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA = Path("/tmp/ob_shoot_data")
OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(exist_ok=True, parents=True)

# ---------- seed ----------
if DATA.exists():
    shutil.rmtree(DATA)

from selftest import render_pdf, fill_bubble, simulate_photo, encode_jpeg
from optibubble.config import TestConfig
from optibubble.hub import Hub

hub = Hub(data_dir=DATA)
cfg = TestConfig(title="Physics Midterm — Form A", subject="Physics",
                 num_questions=24, options_per_question=4, student_id_digits=7)
cfg.ensure_ids(); cfg.randomize_key()
hub.create_test(cfg)
lay, pdf = hub.layout, hub.pdf_path()
flat = render_pdf(pdf)
mm2px = flat.shape[1] / lay.page_w

def make_photo(sid, blank_q=None, faint_q=None):
    img = flat.copy()
    for qn, letter in cfg.answer_key.items():
        if qn == blank_q:
            continue
        idx = "ABCD".index(letter)
        b = [bb for bb in lay.bubbles if bb.kind == "option" and bb.q == qn][idx]
        fill_bubble(img, mm2px, b.cx, b.cy, b.r, "faint" if qn == faint_q else "pen")
    for d, ch in enumerate(sid):
        bb = lay.digit_bubbles(d)[int(ch)]
        fill_bubble(img, mm2px, bb.cx, bb.cy, bb.r, "pen")
    return encode_jpeg(simulate_photo(img, lay, seed=3))

hub._process("shot-a", make_photo("2041986"))
hub._process("shot-b", make_photo("2041987", blank_q=9, faint_q=14))
hub._process("shot-c", make_photo("2041988"))
hub._process("shot-d", make_photo("2041990", blank_q=4, faint_q=17))
hub.log("Server listening on http://192.168.1.20:5000")
hub.log("✔ Sheet 204100 graded — 24/24 · 81 ms")
hub.log("⚑ Sheet 204102 flagged (2 item(s)) → review queue")

print("starting server …")
ok = hub.start_server()
assert ok, hub.server_error
print("server up:", hub.magic_url("127.0.0.1"))

# ---------- shoot ----------
from playwright.sync_api import sync_playwright

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:5000/", wait_until="networkidle")
    time.sleep(1.0)

    def snap(name, el=None):
        time.sleep(0.45)
        (el or page).screenshot(path=str(OUT / name))
        print("📸", name)

    snap("01-dashboard.png")
    page.evaluate("goto('setup')")
    page.fill("#fTitle", "Physics Midterm — Form A")
    page.fill("#fSubject", "Physics")
    page.fill("#fInstructions", "Answer ALL questions. Use a dark pen. Calculators are NOT permitted.")
    page.evaluate("() => { const s = document.getElementById('fHeaderScale'); s.value = 1.2; s.dispatchEvent(new Event('input')); }")
    # pre-fill a few key cells for the screenshot
    page.evaluate("""() => { for (const q of [1,2,3,5,8]) {
        const b = document.querySelector(`[data-q="${q}"]`); if (b) b.click(); } }""")
    snap("02-setup.png")
    page.evaluate("goto('serve')")
    time.sleep(0.6)
    snap("03-serve.png")
    page.evaluate("goto('review')")
    time.sleep(0.8)
    snap("04-review.png")
    page.evaluate("goto('results')")
    time.sleep(0.8)
    snap("05-results.png")
    page.evaluate("goto('settings')")
    time.sleep(0.6)
    snap("06-settings.png")
    page.evaluate("goto('help')")
    snap("07-help.png")

    # mobile page
    mob = browser.new_page(viewport={"width": 390, "height": 844},
                           device_scale_factor=2, is_mobile=True,
                           has_touch=True, user_agent=
                           "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                           "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                           "Mobile/15E148 Safari/604.1")
    mob.on("console", lambda m: errors.append("MOBILE: " + m.text) if m.type == "error" else None)
    mob.goto(hub.magic_url("127.0.0.1").replace("192.168.1.20", "127.0.0.1"),
             wait_until="networkidle")
    time.sleep(0.6)
    mob.screenshot(path=str(OUT / "08-mobile-scanner.png"))
    print("📸 08-mobile-scanner.png")

    browser.close()

hub.stop_server()
print("\nconsole errors:", len(errors))
for e in errors[:10]:
    print("  !", e[:200])
print("DONE →", OUT)
