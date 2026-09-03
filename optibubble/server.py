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
from .storage import CSV_COLUMNS

MAX_CONTENT_LENGTH_MB = 100
WEB_DIR = Path(__file__).resolve().parent / "web"


def _web_path(sub: str, name: str) -> Path:
    base = (WEB_DIR / sub).resolve()
    p = (base / name).resolve()
    if not str(p).startswith(str(base)):
        abort(404)
    return p


def parse_weights_safe(text):
    from .config import TestConfig
    try:
        return TestConfig.parse_weights_text(text or "")
    except ValueError:
        return {}


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
    # ------------------------------------------------------- React SPA ----
    _DIST = WEB_DIR / "dist"

    def _spa(route: str = "app"):
        """Serve the React bundle with a deterministic route marker injected —
        the client must never guess its route from the URL (mobile browsers
        normalise/restore pages unpredictably)."""
        p = _DIST / "index.html"
        if p.exists():
            html = p.read_text(encoding="utf-8")
            marker = f"<script>window.__OB_ROUTE__={route!r};</script>"
            html = html.replace("<head>", f"<head>{marker}", 1)
            return Response(html, mimetype="text/html")
        # No React build available → serve the matching LEGACY page.  A scan
        # link must NEVER fall back to the desktop dashboard.
        fallback = "scan.html" if route == "scanner" else "app.html"
        return send_file(_web_path("", fallback))

    @app.route("/")
    def index():
        return _spa("app")

    @app.route("/scan/<token>")
    def scan(token: str):
        return _spa("scanner")

    @app.route("/app/<path:name>")
    def spa_assets(name: str):
        p = (_DIST / name).resolve()
        if not str(p).startswith(str(_DIST.resolve())) or not p.exists():
            abort(404)
        mime = ("text/javascript" if name.endswith((".js", ".mjs"))
                else "text/css" if name.endswith(".css") else None)
        return send_file(p, mimetype=mime, conditional=True)

    @app.route("/api/selftest", methods=["POST"])
    def run_selftest():
        """Run the end-to-end suite in-process; return the tail output."""
        import io as _io
        import contextlib as _ctx
        import subprocess as _sub
        import sys as _sys
        ok = True
        try:
            proc = _sub.run(
                [_sys.executable, str(Path(__file__).resolve().parent.parent
                                      / "selftest.py")],
                capture_output=True, text=True, timeout=300)
            out = proc.stdout.strip().splitlines()
            ok = proc.returncode == 0
            tail = "\n".join(out[-6:])
        except Exception as e:
            ok, tail = False, f"could not run: {e}"
        return jsonify({"ok": ok, "tail": tail})

    @app.route("/api/system")
    def system_info():
        """System-wide diagnostics for the Settings → System page."""
        import platform
        import sys as _sys
        import cv2 as _cv
        import numpy as _np
        try:
            import PIL
            pil_v = PIL.__version__
        except Exception:
            pil_v = "?"
        try:
            import pymupdf as _pm
            fitz_v = _pm.__doc__.split()[1] if _pm.__doc__ else "?"
        except Exception:
            fitz_v = "-"
        from . import __version__ as appver
        tests_root = hub.data_dir / "tests"
        n_tests = len([d for d in tests_root.iterdir() if d.is_dir()]) \
            if tests_root.exists() else 0
        du_mb = 0.0
        try:
            for p in hub.data_dir.rglob("*"):
                if p.is_file():
                    du_mb += p.stat().st_size
            du_mb = round(du_mb / 1048576, 1)
        except Exception:
            pass
        return jsonify({
            "app": appver, "python": _sys.version.split()[0],
            "platform": f"{platform.system()} {platform.release()} "
                        f"({platform.machine()})",
            "opencv": _cv.__version__, "numpy": _np.__version__,
            "pillow": pil_v, "pymupdf": fitz_v,
            "flask": __import__("flask").__version__,
            "data_dir": str(hub.data_dir), "tests": n_tests,
            "data_mb": du_mb,
            "server": {"http": hub.server_running,
                       "https": hub.https_running,
                       "port": hub.settings.port,
                       "https_port": hub.settings.https_port,
                       "https_mode": hub.settings.https_mode,
                       "https_domain": hub._https_host},
            "stats": hub.stats,
            "lan_ips": hub.lan_ips(),
        })

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
            default_points=float(d.get("default_points", 1.0) or 1.0),
            partial_multi_credit=float(d.get("partial_multi_credit", 0.0) or 0.0),
            weights=parse_weights_safe(d.get("weights_text", "")),
            header_font_scale=float(d.get("header_font_scale", 1.0) or 1.0),
            logo_position=d.get("logo_position", "left"),
            answer_key={int(q): a for q, a in (d.get("answer_key") or {}).items()})
        errs = cfg.validate()
        if errs:
            return jsonify({"errors": errs}), 400
        auto_key = len(cfg.answer_key) == 0
        if auto_key:                      # friendly default: full random key
            cfg.randomize_key()
        missing = cfg.num_questions - len(cfg.answer_key)
        try:
            hub.create_test(cfg, generate_pdf=True)
        except Exception as e:
            return jsonify({"errors": [str(e)]}), 400
        hub.log(f"Test created — {cfg.title} ({cfg.test_id})")
        for w in (hub.layout.warnings if hub.layout else []):
            hub.log(f"ℹ {w}")
        return jsonify({"ok": True, "test_id": cfg.test_id,
                        "missing_key": missing, "auto_key": auto_key,
                        "warnings": (hub.layout.warnings if hub.layout else [])})

    @app.route("/api/key", methods=["POST"])
    def update_key():
        d = request.get_json(silent=True) or {}
        ok = hub.update_key(d.get("entries") or {}, replace=bool(d.get("replace")))
        return jsonify({"ok": ok,
                        "defined": len(hub.test.answer_key) if hub.test else 0,
                        "total": hub.test.num_questions if hub.test else 0}
                       ), (200 if ok else 404)

    @app.route("/api/tests/<test_id>", methods=["GET"])
    def get_test(test_id: str):
        data = hub.storage.load_test(test_id)
        if not data:
            return jsonify({"error": "not found"}), 404
        return jsonify(data)

    @app.route("/api/tests/<test_id>/edit", methods=["POST"])
    def edit_test(test_id: str):
        d = request.get_json(silent=True) or {}
        ok, errs = hub.edit_test(test_id, d)
        return jsonify({"ok": ok, "errors": errs}), (200 if ok else 400)

    @app.route("/api/tests/<test_id>/delete", methods=["POST"])
    def delete_test(test_id: str):
        ok, msg = hub.delete_test(test_id)
        return jsonify({"ok": ok, "message": msg}), (200 if ok else 404)

    @app.route("/api/tests/<test_id>/archive", methods=["POST"])
    def archive_test(test_id: str):
        from .archive import create_archive
        d = request.get_json(silent=True) or {}
        pw = d.get("password") or ""
        if pw and len(pw) < 4:
            return jsonify({"error": "Use a password of 4+ characters "
                                     "(or leave it empty for no encryption)."}), 400
        from .config import tests_dir as _td
        root = _td(hub.data_dir) / test_id
        if not root.exists():
            return jsonify({"error": "not found"}), 404
        blob = create_archive(root, pw)
        return Response(blob, mimetype="application/octet-stream",
                        headers={"Content-Disposition":
                                 f"attachment; filename={test_id}.optibubble"})

    @app.route("/api/archive/restore", methods=["POST"])
    def restore_test():
        from .archive import restore_archive
        from .config import tests_dir as _td
        f = request.files.get("file")
        pw = request.form.get("password") or ""
        if not f:
            return jsonify({"error": "no file"}), 400
        data = f.read()
        if data[:5] == b"OBAR1" and not pw:
            return jsonify({"error": "This archive is encrypted — enter its "
                                     "password."}), 400
        try:
            test_id, n = restore_archive(data, pw, _td(hub.data_dir))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        hub.log(f"Test {test_id} restored from archive ({n} files)")
        return jsonify({"ok": True, "test_id": test_id, "files": n})

    # ------------------------------------------------ desktop USB camera ----
    @app.route("/api/camera/devices")
    def camera_devices():
        return jsonify(hub.camera_devices())

    @app.route("/api/camera/start", methods=["POST"])
    def camera_start():
        d = request.get_json(silent=True) or {}
        ok, msg = hub.camera_start(d.get("index", 0), d.get("synthetic"))
        return jsonify({"ok": ok, "message": msg}), (200 if ok else 400)

    @app.route("/api/camera/stop", methods=["POST"])
    def camera_stop():
        hub.camera_stop()
        return jsonify({"ok": True})

    @app.route("/api/camera/frame.jpg")
    def camera_frame():
        jpg = hub.camera_frame_jpeg()
        if not jpg:
            abort(404)
        return Response(jpg, mimetype="image/jpeg")

    @app.route("/api/camera/grade", methods=["POST"])
    def camera_grade():
        if not hub.test:
            return jsonify({"error": {"code": "NO_TEST",
                                      "message": "Create or open a test first."}}), 400
        jpg = hub.camera_frame_jpeg()
        if not jpg:
            return jsonify({"error": {"code": "NO_CAMERA",
                                      "message": "The camera has no frame yet."}}), 400
        rid, err = hub.accept_upload(hub.test.session_token, jpg)
        if err:
            return jsonify({"error": err}), 400
        return jsonify({"receipt": rid})

    # -------------------------------------------- WebRTC mirror signaling ---
    @app.route("/api/mirror/<slot>", methods=["GET", "POST", "DELETE"])
    def mirror_signal(slot: str):
        if slot not in ("offer", "answer", "bye"):
            abort(404)
        if request.method == "POST":
            hub.mirror_post(slot, request.get_json(silent=True) or {})
            return jsonify({"ok": True})
        if request.method == "DELETE":
            hub.mirror_post(slot, None)
            return jsonify({"ok": True})
        item = hub.mirror_get(slot)
        if not item:
            return jsonify({"payload": None})
        return jsonify(item)

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

    @app.route("/api/key.pdf")
    def key_pdf():
        p = hub.key_pdf_path()
        if not p:
            abort(404)
        return send_file(p, mimetype="application/pdf")

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
                     "crop": _review_img_url(r.get("sheet_id"), f.get("crop"))}
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

    @app.route("/api/analytics")
    def analytics():
        """Psychometrics for the active test: error rates, discrimination
        (point-biserial), KR-20 reliability."""
        import json as _json
        import math as _math
        if not hub.test:
            return jsonify({"error": "no active test"}), 404
        rows = hub.storage.read_results(hub.test)
        sheets = []
        for r in rows:
            try:
                d = _json.loads(r.get("Detailed_Answers_JSON") or "{}")
                sheets.append(d.get("correct") or {})
            except Exception:
                pass
        n = len(sheets)
        nq = hub.test.num_questions
        qs = [q for q in range(1, nq + 1)
              if any(str(q) in s for s in sheets)]
        if n < 2 or not qs:
            return jsonify({"n": n, "kr20": None, "questions": [],
                            "note": "needs at least 2 graded sheets"})
        totals = [sum(1.0 for q in qs if s.get(str(q))) for s in sheets]
        mean = sum(totals) / n
        var = sum((t - mean) ** 2 for t in totals) / n
        qstat = []
        sum_pq = 0.0
        for q in qs:
            p = sum(1.0 for s in sheets if s.get(str(q))) / n
            sum_pq += p * (1 - p)
            # point-biserial: item score vs total score
            m1 = sum(t for t, s in zip(totals, sheets) if s.get(str(q))) / \
                 max(1, sum(1 for s in sheets if s.get(str(q))))
            m0 = sum(t for t, s in zip(totals, sheets) if not s.get(str(q))) / \
                 max(1, sum(1 for s in sheets if not s.get(str(q))))
            rpb = ((m1 - m0) * _math.sqrt(p * (1 - p)) / _math.sqrt(var)
                    if var > 0 else 0.0)
            qstat.append({"q": q, "p_correct": round(p, 3),
                          "error_rate": round(1 - p, 3),
                          "discrimination": round(rpb, 3),
                          "points": hub.test.weight_for(q)})
        k = len(qs)
        kr20 = (k / (k - 1)) * (1 - sum_pq / var) if k > 1 and var > 0 else None
        sorted_t = sorted(totals)
        median = (sorted_t[n // 2] if n % 2 else
                  (sorted_t[n // 2 - 1] + sorted_t[n // 2]) / 2)
        return jsonify({
            "n": n, "k": k, "kr20": round(kr20, 3) if kr20 is not None else None,
            "mean": round(mean, 2), "median": median,
            "stdev": round(_math.sqrt(var), 2), "questions": qstat})

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
        import csv as _csv
        import io as _io
        if not hub.test:
            return jsonify({"error": "no active test"}), 404
        p = hub.storage.test_root(hub.test) / "results.csv"
        buf = _io.StringIO()
        w = _csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
        w.writeheader()
        if p.exists():
            with p.open(newline="", encoding="utf-8") as f:
                for row in _csv.DictReader(f):
                    w.writerow(row)
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition":
                                 f"attachment; filename={hub.test.test_id}_results.csv"})

    @app.route("/api/reviewimg/<sheet_id>/<name>")
    def reviewimg(sheet_id: str, name: str):
        """Serve a review evidence crop by sheet + name — no filesystem paths
        in URLs (robust across OSes and relocated data folders)."""
        import re as _re
        if not hub.test:
            abort(404)
        if not _re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", sheet_id) or \
           not _re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", name):
            abort(404)
        base = (hub.storage.test_root(hub.test) / "review" / "crops").resolve()
        p = (base / sheet_id / f"{name}.png").resolve()
        if not str(p).startswith(str(base)) or not p.exists():
            abort(404)
        return send_file(p, mimetype="image/png")

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
    https = hub.https_url() or "https://<this-pc>:" + str(hub.settings.https_port)
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
<p style="color:#A3A6B1">This browser only allows in-page cameras on secure
connections. Install this computer's local certificate once — it takes under a
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
          → pick <b>OPTIBubble-CA.crt</b> (it belongs to the computer
          serving this page).</li>
      <li>Chrome may still refuse user CAs — if the camera stays black, use
          <b>Firefox</b> (honours user certificates) or the 🖼️ upload button,
          which always works.</li></ol>
  <a class="btn" href="/cert/ca.crt">Download certificate</a>
</div>

<div class="step"><b>Done?</b> Scan the second QR code (white card, “live camera”)
or open:<br><code style="color:#FF7448;word-break:break-all">{https}</code>
<small>Only devices on this local Wi-Fi can reach this server. Removing the
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


def _review_img_url(sheet_id, crop_path) -> str:
    """Build the path-free crop URL from the stored filename."""
    if not crop_path or not sheet_id:
        return ""
    name = str(crop_path).replace("\\", "/").split("/")[-1].removesuffix(".png")
    return f"/api/reviewimg/{sheet_id}/{name}"
