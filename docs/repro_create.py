"""Reproduce the real browser 'create test' flow and capture any failure."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optibubble.hub import Hub
from playwright.sync_api import sync_playwright

hub = Hub(data_dir=Path("/tmp/ob_repro"))
hub.start_server()
url = "http://127.0.0.1:5000/"
print("server up:", url)

fails = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("console", lambda m: fails.append("console: " + m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: fails.append("pageerror: " + str(e)))
    # capture network failures / non-2xx on /api/tests
    pg.on("response", lambda r: fails.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    pg.goto(url, wait_until="networkidle"); time.sleep(0.8)

    pg.evaluate("goto('setup')")
    pg.fill("#fTitle", "Math Quiz 3")
    pg.fill("#fSubject", "Mathematics")
    pg.fill("#fQuestions", "10")

    # Scenario A: create WITHOUT filling the answer key (common user flow!)
    print("A: clicking create with EMPTY key…")
    pg.click("#createBtn"); time.sleep(1.6)
    err = pg.eval_on_selector("#setupErr", "e => e.style.display !== 'none' ? e.textContent : null")
    print("   error shown:", err)
    state = hub.snapshot()
    print("   A created:", state["test"] is not None, "| pdf:", hub.pdf_path() is not None)
    # serve page shows the key card; complete the key there
    pg.evaluate("goto('serve')"); time.sleep(0.8)
    vis = pg.eval_on_selector("#keyCard", "e => e.style.display !== 'none'")
    print("   key card visible:", vis)
    pg.fill("#keyEdit", "ABCDABCDAB"); pg.click("#keySave"); time.sleep(1.0)
    print("   key after save:", len(hub.test.answer_key), "/", hub.test.num_questions)

    # Scenario B: fill full key via paste
    pg.fill("#keyPaste", "ABCDABCDAB")
    pg.click("#keyLoad"); time.sleep(0.3)
    pg.click("#createBtn"); time.sleep(1.5)
    state = hub.snapshot()
    print("B: test created:", state["test"] is not None,
          "| pdf exists:", hub.pdf_path() is not None)

    # check the PDF is real and served
    import urllib.request
    r = urllib.request.urlopen(url + "api/sheet.pdf")
    data = r.read()
    print("   /api/sheet.pdf:", r.status, r.headers.get("Content-Type"),
          len(data), "bytes, header:", data[:8])
    b.close()
hub.stop_server()
print("\nFAILURES CAPTURED:")
for f in fails[:12]:
    print("  !", f[:160])
if not fails:
    print("  none")
