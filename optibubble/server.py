"""
Embedded local web server (Flask + werkzeug) — the entire OPTIBubble UI.

Serves, entirely from the local machine (no CDN, no internet):

Desktop app (the "GUI", Tauri-ready)
    /                       the desktop web application (dashboard → export)
Mobile bridge
    /scan/<token>           the mobile scanner web app
API
    /api/state              snapshot: active test, server, stats, log, tests
    /api/tests              list / create tests
    /api/tests/<id>/open    reopen a saved test
    /api/serve/start|stop   control the LAN server
    /api/qr.png             magic-link QR code
    /api/preview.png        sheet preview render
    /api/sheet.pdf          the printable sheet (opens the print dialog)
    /api/settings           GET / POST advanced fine-tune settings
    /api/review             flagged sheets queue
    /api/review/resolve     apply human overrides → CSV export
    /api/review/discard     drop a flagged sheet
    /api/results            graded results
    /api/results/export.csv downloadable CSV copy
    /api/crop?p=…           cropped evidence image (path-guarded)
    /api/upload/<token>     photo upload from the phone
    /api/receipt/<id>       grading outcome for the phone
Assets: /fonts/*, /assets/*
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from flask import (Flask, Response, jsonify, request, send_file, abort)

from .hub import Hub

MAX_CONTENT_LENGTH_MB = 100
WEB_DIR = Path(__file__).resolve().parent / "web"


def _web_path(sub: str, name: str) -> Path:
    base = (WEB_DIR / sub).resolve()
    p = (base / name).resolve()
    if not str(p).startswith(str(base)):
        abort(404)
    return p


def create_app(hub: Hub) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_MB * 1024 * 1024

    # ------------------------------------------------------------- statics
    @app.route("/fonts/<path:name>")
    def fonts(name: str):
        return send_file(_web_path("fonts", name), mimetype="font/woff2",
                         conditional=True)

    @app.route("/assets/<path:name>")
    def assets(name: str):
        base_assets = (WEB_DIR / "assets").resolve()
        p = (base_assets / name).resolve()
        if not str(p).startswith(str(base_assets)):   # path traversal guard
            abort(404)
        if not p.exists():                             # app.css / app.js live in web root
            p = _web_path("", name)
        return send_file(p, conditional=True)

    @app.route("/api/https/provision", methods=["POST"])
    def https_provision():
        s = hub.settings
        if s.https_mode != "letsencrypt" or not s.acme_domain \
                or not s.duckdns_token:
            return jsonify({"ok": False,
                            "error": "Switch the mode to Trusted and fill in "
                                     "the domain + DuckDNS token first."}), 400
        state = hub.provision_trusted()
        return jsonify({"ok": state["state"] in ("running", "ok"),
                        "state": state})

    @app.route("/api/https/status")
    def https_status():
        from .acme import trusted_cert_valid
        tc, _ = hub.trusted_cert_paths()
        st = hub._prov_state()
        st = dict(st)
        st["serving_trusted"] = bool(hub._https_host)
        st["cert_days_left"] = (trusted_cert_valid(tc, 0) and
                                (x509_days_left(tc)))
        return jsonify(st)

    @app.route("/api/reveal", methods=["POST"])
    def reveal():
        """Open the data folder in the OS file manager (local desktops only)."""
        import subprocess
        import platform
        try:
            if platform.system() == "Windows":
                import os
                os.startfile(str(hub.data_dir))       # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(hub.data_dir)])
            else:
                subprocess.Popen(["xdg-open", str(hub.data_dir)])
            return jsonify({"ok": True})
        except Exception:
            return jsonify({"ok": False})

    @app.route("/api/qr.png")
    def qr_png():
        import io as _io
        import qrcode as _qrcode
        url = request.args.get("url")
        if not url:
            ip = request.args.get("ip") or None
            url = hub.magic_url(ip)
        img = _qrcode.make(url or "http://optibubble.local", box_size=12,
                           border=2).convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        return Response(buf.getvalue(), mimetype="image/png")

    # ------------------------------------------------- local CA / HTTPS help
    @app.route("/cert")
    def cert_page():
        return Response(_cert_landing(hub), mimetype="text/html")

    @app.route("/cert/ca.crt")
    def cert_download():
        p = hub.data_dir / "certs" / "optibubble-ca.crt"
        if not p.exists():
            abort(404)
        return send_file(p, mimetype="application/x-x509-ca-cert",
                         as_attachment=True, download_name="OPTIBubble-CA.crt")

    @app.route("/cert/ca.mobileconfig")
    def cert_ios():
        from .localca import ios_mobileconfig
        p = hub.data_dir / "certs" / "optibubble-ca.crt"
        if not p.exists():
            abort(404)
        import tempfile
        tmp = Path(tempfile.gettempdir()) / "optibubble-ca.mobileconfig"
        tmp.write_bytes(ios_mobileconfig(p))
        return send_file(tmp, mimetype="application/x-apple-aspen-config",
                         as_attachment=True,
                         download_name="OPTIBubble-CA.mobileconfig")

    # ----------------------------------------------------------- pages
    @app.route("/")
    def index():
        return send_file(_web_path("", "app.html"))

    @app.route("/scan/<token>")
    def scan(token: str):
        return send_file(_web_path("", "scan.html"))

    @app.route("/health")
    def health():
        return jsonify({"ok": True, "app": "OPTIBubble", "version":
                        hub.snapshot().get("version")})

    # ------------------------------------------------------- desktop API
    @app.route("/api/state")
    def state():
        return jsonify(hub.snapshot())

    @app.route("/api/tests", methods=["GET", "POST"])
    def tests():
        if request.method == "GET":
            return jsonify(hub.storage.list_tests())
        d = request.get_json(silent=True) or {}
        from .config import TestConfig
        cfg = TestConfig(
            title=d.get("title", "").strip() or "Untitled Test",
            subject=d.get("subject", "").strip() or "General",
            num_questions=int(d.get("num_questions", 20) or 20),
            options_per_question=int(d.get("options_per_question", 4) or 4),
            student_id_digits=int(d.get("student_id_digits", 7)),
            page_size=(d.get("page_size") or "a4").lower(),
            sheet_instructions=d.get("sheet_instructions", "")[:240],
            write_in_fields=d.get("write_in_fields", "Name,Class,Date"),
            header_font_scale=float(d.get("header_font_scale", 1.0) or 1.0),
            logo_position=d.get("logo_position", "left"),
            answer_key={int(q): a for q, a in (d.get("answer_key") or {}).items()})
        errs = cfg.validate()
        if errs:
            return jsonify({"errors": errs}), 400
        missing = cfg.num_questions - len(cfg.answer_key)
        try:
            hub.create_test(cfg, generate_pdf=True)
        except Exception as e:
            return jsonify({"errors": [str(e)]}), 400
        hub.log(f"Test created — {cfg.title} ({cfg.test_id})")
        for w in (hub.layout.warnings if hub.layout else []):
            hub.log(f"ℹ {w}")
        return jsonify({"ok": True, "test_id": cfg.test_id,
                        "missing_key": missing,
                        "warnings": (hub.layout.warnings if hub.layout else [])})

    @app.route("/api/key", methods=["POST"])
    def update_key():
        d = request.get_json(silent=True) or {}
        ok = hub.update_key(d.get("entries") or {})
        return jsonify({"ok": ok,
                        "defined": len(hub.test.answer_key) if hub.test else 0,
                        "total": hub.test.num_questions if hub.test else 0}
                       ), (200 if ok else 404)

    @app.route("/api/tests/<test_id>/open", methods=["POST"])
    def open_test(test_id: str):
        if not hub.open_test(test_id):
            return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True})

    @app.route("/api/serve/start", methods=["POST"])
    def serve_start():
        ok = hub.start_server()
        return jsonify({"ok": ok, "error": hub.server_error,
                        "url": hub.magic_url() if ok else ""})

    @app.route("/api/serve/stop", methods=["POST"])
    def serve_stop():
        hub.stop_server()
        return jsonify({"ok": True})

    @app.route("/api/preview.png")
    def preview():
        data = hub.preview_png()
        if not data:
            abort(404)
        return Response(data, mimetype="image/png")

    @app.route("/api/sheet.pdf")
    def sheet_pdf():
        p = hub.pdf_path()
        if not p:
            abort(404)
        return send_file(p, mimetype="application/pdf")

    @app.route("/api/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "GET":
            return jsonify(hub.settings.to_dict())
        changes = request.get_json(silent=True) or {}
        hub.update_settings(changes)
        return jsonify(hub.settings.to_dict())

    @app.route("/api/review", methods=["GET"])
    def review_list():
        items = hub.storage.pending_reviews(hub.test) if hub.test else []
        out = []
        for it in items:
            r = it["result"]
            out.append({
                "sheet_id": r.get("sheet_id"),
                "student_id": r.get("student_id", ""),
                "score": r.get("score", 0), "max_score": r.get("max_score", 0),
                "ts": r.get("ts", ""),
                "source_image": it.get("source_image", ""),
                "flags": [
                    {"kind": f.get("kind"), "q": f.get("q"), "digit": f.get("digit"),
                     "guess": f.get("guess"), "message": f.get("message", ""),
                     "crop": (f"/api/crop?p=" + quote(str(f.get("crop", "")))
                              if f.get("crop") else "")}
                    for f in r.get("flags", [])],
            })
        return jsonify(out)

    @app.route("/api/review/resolve", methods=["POST"])
    def review_resolve():
        d = request.get_json(silent=True) or {}
        sheet_id = d.get("sheet_id")
        if not sheet_id:
            return jsonify({"error": "sheet_id required"}), 400
        answers = {int(q): a for q, a in (d.get("answers") or {}).items()}
        ok = hub.resolve_flagged(sheet_id, answers, d.get("student_id"))
        return jsonify({"ok": ok}), (200 if ok else 404)

    @app.route("/api/review/discard", methods=["POST"])
    def review_discard():
        d = request.get_json(silent=True) or {}
        ok = hub.discard_flagged(d.get("sheet_id", ""))
        return jsonify({"ok": ok}), (200 if ok else 404)

    @app.route("/api/results")
    def results():
        if not hub.test:
            return jsonify([])
        rows = hub.storage.read_results(hub.test)
        import json as _json
        for r in rows:
            try:
                r["confidence"] = _json.loads(r.get("Detailed_Answers_JSON", "{}") \
                                              or "{}").get("confidence")
            except Exception:
                r["confidence"] = None
        return jsonify(rows)

    @app.route("/api/results/export.csv")
    def results_export():
        if not hub.test:
            abort(404)
        p = hub.storage.test_root(hub.test) / "results.csv"
        if not p.exists():
            abort(404)
        return send_file(p, as_attachment=True,
                         download_name=f"{hub.test.test_id}_results.csv")

    @app.route("/api/crop")
    def crop():
        p = request.args.get("p", "")
        path = Path(p).resolve()
        if not str(path).startswith(str(hub.data_dir.resolve())):
            abort(403)
        if not path.exists():
            abort(404)
        return send_file(path, mimetype="image/png")

    # ------------------------------------------------------------ mobile
    @app.route("/api/info/<token>")
    def info(token: str):
        if not hub.test or token != hub.test.session_token:
            return jsonify({"error": "BAD_SESSION"}), 404
        t = hub.test
        return jsonify({"title": t.title, "subject": t.subject,
                        "questions": t.num_questions,
                        "options": t.options_per_question,
                        "test_id": t.test_id, "server_ok": True,
                        "quality": hub.settings.jpeg_quality,
                        "width": hub.settings.target_width_px})

    @app.route("/api/upload/<token>", methods=["POST"])
    def upload(token: str):
        if "photo" not in request.files:
            return jsonify({"error": {"code": "NO_FILE",
                                      "message": "No photo in the request."}}), 400
        data = request.files["photo"].read()
        rid, err = hub.accept_upload(token, data)
        if err:
            return jsonify({"error": err}), 403 if err["code"] == "BAD_SESSION" else 400
        return jsonify({"receipt": rid})

    @app.route("/api/receipt/<rid>")
    def receipt(rid: str):
        return jsonify(hub.get_receipt(rid))

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api"):
            return jsonify({"error": "not found"}), 404
        return Response(
            "<h2 style=\"font-family:sans-serif\">404 — nothing here. "
            "Scan the QR code shown in the OPTIBubble app.</h2>",
            mimetype="text/html"), 404

    return app


def _cert_landing(hub) -> str:
    https = hub.https_url() or "https://<teacher-ip>:" + str(hub.settings.https_port)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Enable the live camera — OPTIBubble</title>
<style>
body{{margin:0;background:#0C0D11;color:#EAEBEF;font-family:'Open Sans',system-ui,sans-serif;
line-height:1.55;font-size:14px}}
main{{max-width:520px;margin:0 auto;padding:26px 18px 40px}}
h1{{font-size:17px;margin:8px 0 4px}}
.step{{background:#131419;border-radius:6px;padding:14px 16px;margin:10px 0}}
.step b{{color:#FF7448}}
a.btn{{display:block;text-align:center;text-decoration:none;background:#FF5A2D;color:#160B06;
font-weight:800;padding:12px;border-radius:5px;margin:10px 0 6px}}
small{{color:#8B99B0;display:block;margin-top:4px}}
ol{{padding-left:20px;color:#A3A6B1}} ol b{{color:#EAEBEF}}
</style></head><body><main>
<p style="letter-spacing:.18em;font-size:10px;color:#686C79;font-weight:800">OPTIBubble · Secure Camera</p>
<h1>Unlock the live viewfinder</h1>
<p style="color:#A3A6B1">Your browser only allows in-page cameras on secure
connections. Install the teacher's local certificate once — it takes under a
minute — then every future scan opens the live camera automatically.</p>

<div class="step"><b>iPhone / iPad</b>
  <ol><li>Tap <b>Install profile</b> below, allow the download.</li>
      <li>Open <b>Settings</b> → the <b>Profile Downloaded</b> banner → <b>Install</b>
          (enter passcode if asked).</li>
      <li>Settings → <b>General</b> → <b>About</b> → <b>Certificate Trust Settings</b> →
          enable <b>OPTIBubble Local CA</b>.</li></ol>
  <a class="btn" href="/cert/ca.mobileconfig">Install profile</a>
</div>

<div class="step"><b>Android</b>
  <ol><li>Download the certificate below.</li>
      <li>Settings → <b>Security</b> → <b>Install a certificate</b> → <b>CA certificate</b>
          → pick <b>OPTIBubble-CA.crt</b> (looks scary; it is your teacher's own
          classroom server).</li>
      <li>Chrome may still refuse user CAs — if the camera stays black, use
          <b>Firefox</b> (honours user certificates) or the 🖼️ upload button,
          which always works.</li></ol>
  <a class="btn" href="/cert/ca.crt">Download certificate</a>
</div>

<div class="step"><b>Done?</b> Scan the second QR code (white card, “live camera”)
or open:<br><code style="color:#FF7448;word-break:break-all">{https}</code>
<small>Only devices on this classroom Wi-Fi can reach this server. Removing the
certificate after class: Settings → Profiles / credential storage.</small>
</div>
</main></body></html>"""


def x509_days_left(path) -> int:
    try:
        from cryptography import x509 as _x
        import datetime as _dt
        c = _x.load_pem_x509_certificate(Path(path).read_bytes())
        return (c.not_valid_after_utc - _dt.datetime.now(_dt.timezone.utc)).days
    except Exception:
        return -1
