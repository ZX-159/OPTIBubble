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
        ip = request.args.get("ip") or None
        return Response(hub.magic_qr_png(ip), mimetype="image/png")

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
            header_font_scale=float(d.get("header_font_scale", 1.0) or 1.0),
            logo_position=d.get("logo_position", "left"),
            answer_key={int(q): a for q, a in (d.get("answer_key") or {}).items()})
        errs = cfg.validate()
        missing = cfg.num_questions - len(cfg.answer_key)
        if errs or missing > 0:
            return jsonify({"errors": errs or [
                f"Answer key incomplete — {missing} question(s) missing."]}), 400
        try:
            hub.create_test(cfg, generate_pdf=True)
        except Exception as e:
            return jsonify({"errors": [str(e)]}), 400
        hub.log(f"Test created — {cfg.title} ({cfg.test_id})")
        for w in (hub.layout.warnings if hub.layout else []):
            hub.log(f"ℹ {w}")
        return jsonify({"ok": True, "test_id": cfg.test_id,
                        "warnings": (hub.layout.warnings if hub.layout else [])})

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
