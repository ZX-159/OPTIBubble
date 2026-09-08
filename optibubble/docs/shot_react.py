"""Screenshot the React SPA (all pages + mobile scanner) into docs/screenshots."""
import shutil, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA = Path("/tmp/ob_shoot_spa")
OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(exist_ok=True, parents=True)

if DATA.exists():
    shutil.rmtree(DATA)

from selftest import render_pdf, fill_bubble, simulate_photo, encode_jpeg
from optibubble.config import TestConfig
from optibubble.hub import Hub
from optibubble.sheet_generator import render_pdf_preview

hub = Hub(data_dir=DATA)
cfg = TestConfig(title="Physics Midterm — Form A", subject="Physics",
                 num_questions=24, options_per_question=4, student_id_digits=7)
cfg.ensure_ids(); cfg.randomize_key()
hub.create_test(cfg)
lay, flat = hub.layout, render_pdf(hub.pdf_path())
mm2px = flat.shape[1] / lay.page_w

def make(sid, blank_q=None, faint_q=None):
    img = flat.copy()
    for qn, letter in cfg.answer_key.items():
        if qn == blank_q:
            continue
        b = [bb for bb in lay.bubbles if bb.kind == "option" and bb.q == qn][
            "ABCD".index(letter)]
        fill_bubble(img, mm2px, b.cx, b.cy, b.r, "faint" if qn == faint_q else "pen")
    for d, ch in enumerate(sid):
        bb = lay.digit_bubbles(d)[int(ch)]
        fill_bubble(img, mm2px, bb.cx, bb.cy, bb.r, "pen")
    hub._process("shot-" + sid, encode_jpeg(simulate_photo(img, lay, seed=3)))

make("2041986")
make("2041987", blank_q=9, faint_q=14)
make("2041990", blank_q=4, faint_q=17)
hub.log("✔ Sheet 204100 graded — 24/24 · 81 ms")
hub.log("⚑ Sheet 204102 flagged (2 item(s)) → review queue")
ok = hub.start_server()
assert ok, hub.server_error

from playwright.sync_api import sync_playwright
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900},
                            device_scale_factor=2)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto("http://127.0.0.1:5000/", wait_until="networkidle")
    time.sleep(2.0)

    def snap(name):
        time.sleep(0.6)
        page.screenshot(path=str(OUT / name))
        print("📸", name)

    snap("01-dashboard.png")
    # setup via content link (hero step 1)
    page.click("text=Create a test"); time.sleep(0.8)
    page.fill("input[placeholder*='Physics Midterm']", "Physics Midterm — Form A")
    snap("02-setup.png")
    page.click("[data-testid='nav-serve']"); time.sleep(1.2)
    snap("03-serve.png")
    page.click("[data-testid='nav-review']"); time.sleep(1.4)
    snap("04-review.png")
    page.click("[data-testid='nav-results']"); time.sleep(1.4)
    snap("05-results.png")
    page.click("[data-testid='nav-settings']"); time.sleep(1.2)
    snap("06-settings.png")
    page.click("[data-testid='nav-help']"); time.sleep(0.8)
    snap("07-help.png")

    mob = browser.new_page(viewport={"width": 390, "height": 844},
                           device_scale_factor=2, is_mobile=True, has_touch=True,
                           ignore_https_errors=True)
    mob.on("pageerror", lambda e: errors.append("MOBILE " + str(e)))
    mob.goto(hub.magic_url("127.0.0.1"), wait_until="networkidle")
    time.sleep(1.6)
    mob.screenshot(path=str(OUT / "08-mobile-scanner.png"))
    print("📸 08-mobile-scanner.png")
    browser.close()

hub.stop_server()
print("\nconsole/page errors:", len(errors))
for e in errors[:8]:
    print("  !", e[:160])
print("DONE →", OUT)
