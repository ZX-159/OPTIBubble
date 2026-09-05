"""
Hub — the runtime controller shared by the desktop GUI and the CLI.

Owns:
* the active test (config + sheet layout + session folder),
* advanced settings (persisted to ``settings.json``),
* the embedded Flask server (werkzeug, run in a background thread),
* upload receipts & the processing thread-pool,
* an event queue the GUI polls (sheet graded / flagged / errors …).
"""

from __future__ import annotations

import io
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import qrcode
from werkzeug.serving import make_server

from .config import AdvancedSettings, TestConfig, default_data_dir, settings_path
from .layout import SheetLayout
from .omr_engine import GradeResult, OMRReject, grade_photo
from .sheet_generator import generate_key_pdf, generate_sheet_pdf, render_pdf_preview
from .storage import Storage, result_from_json


def _version() -> str:
    from . import __version__
    return __version__


class Hub:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = AdvancedSettings.load(settings_path(self.data_dir))
        self.storage = Storage(self.data_dir)

        self.test: Optional[TestConfig] = None
        self.layout: Optional[SheetLayout] = None

        self.log_ring: List[dict] = []           # last N events for the web UI
        self.receipts: Dict[str, dict] = {}
        self._receipt_lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="omr")

        self._server = None
        self._server_thread: Optional[threading.Thread] = None
        self._https_server = None
        self._https_thread: Optional[threading.Thread] = None
        self._flask_app = None
        self._https_host: Optional[str] = None
        self._https_days: Optional[int] = None
        self._server_error: str = ""

        from .camera import CameraWorker
        self.camera = CameraWorker()
        self._mirror: dict = {"offer": None, "answer": None, "bye": None}
        self._mirror_lock = threading.Lock()
        self._preview_cache: tuple = ()         # (mtime, bytes)
        self._seen_ids: Dict[str, float] = {}   # student_id → last ts (dedupe hints)

        self.stats = {"sheets_received": 0, "auto_graded": 0,
                      "flagged": 0, "rejected": 0}

    # ------------------------------------------------------------------ events
    def emit(self, type_: str, **payload) -> None:
        ev = {"type": type_, "ts": time.time(), **payload}
        self.log_ring.append(ev)
        del self.log_ring[:-400]                 # keep the last 400 entries

    def log(self, message: str, level: str = "info") -> None:
        self.emit("log", message=message, level=level)

    # ------------------------------------------------------------------ state
    def snapshot(self) -> dict:
        """Everything the desktop web UI needs for one refresh tick."""
        pending = self.storage.pending_reviews(self.test) if self.test else []
        results = self.storage.read_results(self.test) if self.test else []
        return {
            "version": _version(),
            "data_dir": str(self.data_dir),
            "test": (self.test.to_dict() | {"key_complete": len(self.test.answer_key)
                                            >= self.test.num_questions})
                    if self.test else None,
            "has_pdf": self.pdf_path() is not None,
            "server": {"running": self.server_running,
                       "error": self.server_error,
                       "port": self.settings.port, "host": self.settings.host,
                       "https_port": self.settings.https_port,
                       "https_running": self.https_running,
                       "https_mode": self.settings.https_mode,
                       "https_domain": (self._https_host or ""),
                       "https_days": self._https_days,
                       "ips": self.lan_ips(),
                       "url": self.magic_url() if self.test else ""},
            "stats": {**self.stats,
                      "exported": len(results),
                      "pending_review": len(pending)},
            "log": self.log_ring[-80:],
        }

    def update_settings(self, changes: dict) -> AdvancedSettings:
        for k, v in (changes or {}).items():
            if hasattr(self.settings, k):
                cur = getattr(self.settings, k)
                try:
                    if isinstance(cur, bool):
                        setattr(self.settings, k, bool(v))
                    elif isinstance(cur, int):
                        setattr(self.settings, k, int(v))
                    elif isinstance(cur, float):
                        setattr(self.settings, k, float(v))
                    else:
                        setattr(self.settings, k, str(v))
                except (TypeError, ValueError):
                    continue
        self.save_settings()
        return self.settings

    def preview_png(self) -> Optional[bytes]:
        """PNG preview of the current sheet PDF (cached by mtime, PyMuPDF)."""
        p = self.pdf_path()
        if not p:
            return None
        mtime = p.stat().st_mtime
        if self._preview_cache and self._preview_cache[0] == mtime:
            return self._preview_cache[1]
        out = self.storage.test_root(self.test) / "sheet_preview.png"
        if render_pdf_preview(p, out, dpi=110) is None:
            return None
        data = out.read_bytes()
        self._preview_cache = (mtime, data)
        return data

    # ------------------------------------------------------------------ tests
    def create_test(self, test: TestConfig, generate_pdf: bool = True) -> None:
        errs = test.validate()
        if errs:
            raise ValueError("; ".join(errs))
        test.ensure_ids()
        self.storage.create_session(test)
        self.layout = SheetLayout.build(test)
        self.storage.save_test(test, self.layout)
        if generate_pdf:
            generate_sheet_pdf(test, self.storage.test_root(test) / "sheet.pdf",
                               self.layout)
            try:
                generate_key_pdf(test, self.storage.test_root(test) / "key.pdf")
            except Exception:
                pass
        self.test = test
        self.emit("test_created", test_id=test.test_id, title=test.title)

    def key_pdf_path(self) -> Optional[Path]:
        if not self.test:
            return None
        p = self.storage.test_root(self.test) / "key.pdf"
        return p if p.exists() else None

    def pdf_path(self) -> Optional[Path]:
        if not self.test:
            return None
        p = self.storage.test_root(self.test) / "sheet.pdf"
        return p if p.exists() else None

    def update_key(self, entries: dict, replace: bool = False) -> bool:
        """Merge (or replace) answer-key entries in the active test.

        Returns True if at least one valid entry was applied. Letters outside
        the test's allowed options and out-of-range questions are silently
        dropped (not rejected) so a partial key can still be edited — but the
        count is surfaced in the log so the UI can warn about dropped entries.
        """
        if not self.test:
            return False
        k = self.test.options_per_question
        letters = "ABCDEFGHIJ"[:k]
        if replace:
            self.test.answer_key = {}
        applied = dropped = 0
        for q, a in (entries or {}).items():
            try:
                qn = int(q)
            except (TypeError, ValueError):
                dropped += 1
                continue
            if 1 <= qn <= self.test.num_questions and a in letters:
                self.test.answer_key[qn] = a
                applied += 1
            else:
                dropped += 1
        self.storage.save_test(self.test, self.layout)
        complete = len(self.test.answer_key) >= self.test.num_questions
        note = ""
        if dropped:
            allowed = f"A-{letters[-1]}"
            note = (f" · {dropped} entr{'y' if dropped == 1 else 'ies'} skipped "
                    f"(valid: {allowed}, questions 1-{self.test.num_questions})")
        self.log(f"Answer key updated — {len(self.test.answer_key)}/"
                 f"{self.test.num_questions} defined{note}"
                 + ("" if complete else " (grading scores defined questions only)"))
        # True when anything was applied, or when there was nothing to apply
        # (a no-op save still "succeeds").
        return applied > 0 or not (entries or {})

    # ------------------------------------------------------------- management
    EDITABLE_FIELDS = ("title", "subject", "sheet_instructions",
                       "header_font_scale", "logo_position", "write_in_fields")
    STRUCTURAL_FIELDS = ("num_questions", "options_per_question",
                         "student_id_digits", "page_size")

    def delete_test(self, test_id: str) -> Tuple[bool, str]:
        """Remove a saved test and all its data. Returns (ok, message)."""
        import shutil
        from .config import tests_dir as _tests_dir
        root = _tests_dir(self.data_dir) / test_id
        if not root.exists():
            return False, "No such test."
        if self.test and self.test.test_id == test_id:
            # NB: never stop the HTTP server here — the desktop app UI itself
            # is served from it. Just drop the active-test context.
            self.test, self.layout = None, None
            self._preview_cache = ()
            self.emit("test_closed")
        try:
            shutil.rmtree(root)
        except OSError as e:
            return False, f"Could not delete: {e}"
        self.log(f"Test {test_id} deleted")
        self.emit("tests_changed")
        return True, "deleted"

    def edit_test(self, test_id: str, changes: dict) -> Tuple[bool, List[str]]:
        """Edit metadata/design/answer key of a saved (or active) test.

        Structural fields (question count, options, paper, ID digits) cannot
        change after creation — printed sheets would no longer match.
        """
        data = self.storage.load_test(test_id)
        if not data:
            return False, ["Test not found."]
        t = TestConfig.from_dict(data["test"])

        structural = [f for f in self.STRUCTURAL_FIELDS
                      if f in changes and str(changes.get(f)) != str(getattr(t, f))]
        if structural:
            return False, [
                "Question count, options, ID digits and paper size can't change "
                "after creation (printed sheets would mismatch). Create a new "
                "test instead."]

        key_changed = False
        for f in self.EDITABLE_FIELDS:
            if f in changes:
                setattr(t, f, changes[f])
        if "answer_key" in changes and changes["answer_key"] is not None:
            t.answer_key = {int(q): a for q, a in changes["answer_key"].items()}
            key_changed = True
        errs = t.validate()
        if errs:
            return False, errs

        layout = SheetLayout.from_dict(data.get("layout", {}))
        if not layout.questions:
            layout = SheetLayout.build(t)
        self.storage.save_test(t, layout)
        if self.test and self.test.test_id == test_id:
            self.test, self.layout = t, layout
        # cheap and always correct: refresh the printable sheet + key
        try:
            generate_sheet_pdf(t, self.storage.test_root(t) / "sheet.pdf", layout)
        except Exception:
            pass
        try:
            generate_key_pdf(t, self.storage.test_root(t) / "key.pdf")
        except Exception:
            pass
        self.log(f"Test edited — {t.title} ({t.test_id})"
                 + (" · answer key replaced" if key_changed else ""))
        self.emit("tests_changed")
        return True, []

    def open_test(self, test_id: str) -> bool:
        data = self.storage.load_test(test_id)
        if not data:
            return False
        test = TestConfig.from_dict(data["test"])
        layout = SheetLayout.from_dict(data.get("layout", {}))
        if not layout.questions:          # legacy/missing layout → rebuild
            layout = SheetLayout.build(test)
        self.test, self.layout = test, layout
        self.emit("test_opened", test_id=test.test_id, title=test.title)
        return True

    # ------------------------------------------------------------------ server
    def lan_ips(self) -> List[str]:
        """Best-effort enumeration of the machine's IPv4 LAN addresses.

        Avoids the classic `connect(("8.8.8.8", 80))` trick, which only works
        when a default route exists — on an offline box it throws, so the QR
        link would fall back to 127.0.0.1 and be unreachable by phones. We
        enumerate hostname-based AND socket-interface addresses instead.
        """
        ips: List[str] = []
        # 1 · hostname A-records (works without a default route)
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None,
                                           socket.AF_INET):
                ip = info[4][0]
                if ip not in ips and not ip.startswith("127."):
                    ips.append(ip)
        except Exception:
            pass
        # 2 · actual interface-bound sockets (catches addresses a hostname
        #     lookup misses, incl. multi-homed machines)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # connect to a route-independent, non-routable address so the OS
            # just picks an interface without sending anything
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
            s.close()
        except Exception:
            pass
        # 3 · platform interface enumeration (Windows / macOS / Linux)
        try:
            import platform
            if platform.system() == "Windows":
                import subprocess
                out = subprocess.run(
                    ["ipconfig"], capture_output=True, text=True, timeout=4
                ).stdout
                import re
                for m in re.finditer(r"IPv4 Address[^:]*:\s*([0-9.]+)", out):
                    ip = m.group(1)
                    if ip not in ips and not ip.startswith("127.") and ip != "0.0.0.0":
                        ips.append(ip)
            else:
                import subprocess
                out = subprocess.run(
                    ["ip", "-4", "addr", "show"], capture_output=True,
                    text=True, timeout=4
                ).stdout
                import re
                for m in re.finditer(r"inet\s+([0-9.]+)/", out):
                    ip = m.group(1)
                    if ip not in ips and not ip.startswith("127.") and ip != "0.0.0.0":
                        ips.append(ip)
        except Exception:
            pass
        return ips or ["127.0.0.1"]

    def magic_url(self, ip: Optional[str] = None) -> str:
        if not self.test:
            return ""
        ip = ip or self.lan_ips()[0]
        return f"http://{ip}:{self.settings.port}/scan/{self.test.session_token}"

    def magic_qr_png(self, ip: Optional[str] = None) -> bytes:
        url = self.magic_url(ip) or "http://optibubble.local"
        img = qrcode.make(url, box_size=12, border=2).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def start_server(self) -> bool:
        if self._server is not None:
            return True
        from .server import create_app
        self._server_error = ""
        try:
            app = create_app(self)
            self._flask_app = app
            try:
                self._server = make_server(self.settings.host,
                                           self.settings.port, app, threaded=True)
            except (OSError, SystemExit):
                # port busy (werkzeug raises SystemExit, not OSError!) →
                # probe the next few ports and persist what binds
                bound = None
                for cand in range(self.settings.port + 1, self.settings.port + 10):
                    try:
                        bound = make_server(self.settings.host, cand, app,
                                            threaded=True)
                        break
                    except (OSError, SystemExit):
                        continue
                if bound is None:
                    raise
                self._server = bound
                self.log(f"Port {self.settings.port} was busy — using "
                         f"{cand} (saved)", "warn")
                self.settings.port = cand
                self.save_settings()
            self._server_thread = threading.Thread(target=self._server.serve_forever,
                                                   name="optibubble-server", daemon=True)
            self._server_thread.start()
        except (OSError, SystemExit) as e:
            self._server = None
            self._server_error = (str(e) or "port already in use").splitlines()[-1]
            self.emit("server_error", error=self._server_error)
            return False
        if self.settings.enable_https:
            self._start_https(app)
        self.emit("server_started", url=self.magic_url())
        return True

    def trusted_cert_paths(self):
        d = self.data_dir / "certs"
        return d / "trusted-fullchain.pem", d / "trusted-key.pem"

    # ------------------------------------------------------------------ HTTPS
    PROVISION_STEPS = [
        ("check",   "Checking your setup"),
        ("account", "Contacting Let's Encrypt"),
        ("dns",     "Publishing the DNS challenge"),
        ("wait",    "Waiting for DNS (up to 3 min)"),
        ("issue",   "Issuing the certificate"),
        ("activate","Activating on this PC"),
    ]

    def _prov_state(self) -> dict:
        return getattr(self, "_https_provision",
                       {"state": "idle", "steps": [], "error": "",
                        "detail": "", "domain": "", "ts": 0})

    def _prov_step(self, step_id: str, status: str, detail: str = "") -> None:
        p = self._prov_state()
        p["steps"] = [{"id": i, "label": l,
                       "status": (status if i == step_id else
                                  next((s["status"] for s in p["steps"]
                                        if s["id"] == i), "pending")),
                       "detail": (detail if i == step_id else
                                  next((s["detail"] for s in p["steps"]
                                        if s["id"] == i), ""))}
                     for i, l in self.PROVISION_STEPS]
        self._https_provision = p
        self.emit("https_progress")

    def provision_trusted(self) -> dict:
        """Guided, observable Let's Encrypt issuance (runs in a thread)."""
        import threading as _th
        p = self._prov_state()
        if p["state"] == "running":
            return p
        s = self.settings
        self._https_provision = {"state": "running", "steps": [], "error": "",
                                 "detail": "", "domain": s.acme_domain,
                                 "ts": time.time()}

        def fail(step_id: str, message: str, hint: str = "") -> None:
            self._https_provision["state"] = "error"
            self._https_provision["error"] = message
            self._https_provision["hint"] = hint
            self._prov_step(step_id, "error", message)
            self.log(f"⚠ live-camera setup failed: {message}", "warn")
            self.emit("https_progress")

        def run():
            from .acme import (ACMEClient, DIR_STAGING, DIR_PROD, dns_a_lookup,
                               issue_trusted_cert, make_csr, trusted_cert_valid)
            try:
                # -- 1 · preflight ------------------------------------------
                self._prov_step("check", "active")
                dom, tok = s.acme_domain, s.duckdns_token
                if not dom.endswith(".duckdns.org") or len(dom.split(".")) != 3:
                    return fail("check", "Use a duckdns.org subdomain",
                                "e.g. myclass.duckdns.org — create one free at "
                                "duckdns.org")
                if len(tok) < 8:
                    return fail("check", "DuckDNS token missing",
                                "Copy the token from the top of duckdns.org")
                ips = [i for i in self.lan_ips() if not i.startswith("127.")]
                resolved = dns_a_lookup(dom)
                if not resolved:
                    return fail("check", "Can't reach DNS — is this PC online?",
                                "Issuing needs internet once; scans never do")
                if ips and resolved and not (set(resolved) & set(ips)):
                    return fail("check",
                                f"{dom} points at {resolved[0]}, but this PC is "
                                f"{ips[0]}",
                                "Open duckdns.org → set the domain's IP to "
                                f"{ips[0]} → press Start again (takes effect in "
                                "≈1 min)")
                self._prov_step("check", "done")

                # -- 2-5 · issue (progress comes back via steps) -------------
                self._prov_step("account", "active")
                out_dir = self.data_dir / "certs"
                cert_p, key_p = self._issue_with_progress(s, out_dir, fail)
                if not cert_p:
                    return
                self._prov_step("activate", "active")
                self._restart_https()
                self._prov_step("activate", "done")
                self._https_provision["state"] = "ok"
                self._https_provision["expires"] = trusted_cert_valid(
                    cert_p, 0)
                self.log(f"🔒 live camera ready — https://{dom}:"
                         f"{s.https_port} (no student setup needed)", "ok")
                self.emit("https_progress")
            except Exception as e:
                fail("issue", str(e)[:200])

        _th.Thread(target=run, name="optibubble-acme", daemon=True).start()
        return self._prov_state()

    def _issue_with_progress(self, s, out_dir, fail):
        """Drive acme.issue_trusted_cert while reporting step transitions."""
        from .acme import ACMEClient, DIR_PROD, issue_trusted_cert
        step_map = {"account": "account", "dns": "dns", "wait": "wait",
                    "issue": "issue"}
        last = {"n": 0}

        def progress(msg: str) -> None:
            self.log("🔒 " + msg)
            if "ACME account" in msg:
                self._prov_step("account", "done")
                self._prov_step("dns", "active")
            elif "DNS-01 challenge" in msg:
                self._prov_step("dns", "done")
                self._prov_step("wait", "active")
            elif "propagation" in msg:
                last["n"] += 1
                self._prov_step("wait", "active",
                                f"{last['n'] * 15}s elapsed" if last["n"] > 1
                                else "")
            elif "TXT record did not propagate" in msg:
                fail("wait", "DNS did not confirm the record in time",
                     "Check the token at duckdns.org, then press Start again")
            elif "certificate issued" in msg:
                self._prov_step("wait", "done")
                self._prov_step("issue", "done")

        try:
            return issue_trusted_cert(
                s.acme_domain, s.duckdns_token,
                s.acme_email or "teacher@example.com", out_dir,
                progress_every=15, log=progress)
        except Exception as e:
            fail("issue", str(e)[:200])
            return None

    def _start_https(self, app) -> None:
        """Serve the same app over TLS — trusted cert when configured, else
        the built-in local CA."""
        try:
            import ssl
            cert_dir = self.data_dir / "certs"
            from .acme import trusted_cert_valid
            tc, tk = self.trusted_cert_paths()
            if (self.settings.https_mode == "letsencrypt"
                    and self.settings.acme_domain and trusted_cert_valid(tc, 0)):
                leaf_c, leaf_k = tc, tk
                self._https_host = self.settings.acme_domain
                try:
                    from cryptography import x509 as _x
                    import datetime as _dt
                    _c = _x.load_pem_x509_certificate(tc.read_bytes())
                    self._https_days = (_c.not_valid_after_utc - _dt.datetime.now(
                        _dt.timezone.utc)).days
                except Exception:
                    self._https_days = None
                if not trusted_cert_valid(tc, 30):
                    self.log("🔒 trusted certificate expiring soon — "
                             "renewing in the background")
                    self.provision_trusted()
                self.log(f"🔒 serving trusted HTTPS for "
                         f"{self.settings.acme_domain}")
            else:
                self._https_host = None
                self._https_days = None
                from .localca import ensure_ca, load_ca, issue_leaf
                ca_cert_p, ca_key_p = ensure_ca(cert_dir)
                ca_cert, ca_key = load_ca(ca_cert_p, ca_key_p)
                leaf_c, leaf_k = issue_leaf(ca_cert, ca_key, self.lan_ips(),
                                            cert_dir / "server.crt",
                                            cert_dir / "server.key")
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(str(leaf_c), str(leaf_k))
            srv = make_server(self.settings.host, self.settings.https_port, app,
                              threaded=True)
            srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
            self._https_server = srv
            self._https_thread = threading.Thread(
                target=srv.serve_forever, name="optibubble-https", daemon=True)
            self._https_thread.start()
            host_note = (f" for {self._https_host}" if self._https_host
                         else " (install code A once)")
            self.log(f"🔒 HTTPS bridge ready on :{self.settings.https_port}"
                     f"{host_note}")
            # Always arm the renewal watcher on the HTTPS listener, not just
            # after a manual re-issue. A fresh cold start whose cert isn't yet
            # near expiry would otherwise never run it and lapse mid-lesson.
            self._start_renewal_monitor()
        except Exception as e:
            self._https_server = None
            self.log(f"⚠ HTTPS bridge unavailable ({e}) — the scanner falls "
                     "back to the native camera app", "warn")

    def _restart_https(self) -> None:
        """Swap the TLS listener to the newest certificate without stopping
        the app (used right after a certificate is issued)."""
        if self._https_server is not None:
            try:
                self._https_server.shutdown()
            except Exception:
                pass
            self._https_server = None
        if self._flask_app is not None:
            self._start_https(self._flask_app)
        self._start_renewal_monitor()

    def _start_renewal_monitor(self) -> None:
        """Watch the trusted cert and renew ~30 days before expiry so a
        long-running server never lets the Let's Encrypt cert lapse. Renewal
        used to run only at server start, which was fine for short sessions
        but let a weeks-long classroom server expire mid-lesson."""
        if getattr(self, "_renew_mon", None) and self._renew_mon.is_alive():
            return
        from .acme import trusted_cert_valid

        def monitor() -> None:
            while True:
                time.sleep(6 * 3600)          # every 6 hours
                if not self._https_server:
                    break
                if (self.settings.https_mode == "letsencrypt"
                        and self.settings.acme_domain
                        and not trusted_cert_valid(self.trusted_cert_paths()[0], 30)):
                    self.log("🔒 trusted certificate near expiry — renewing "
                             "in the background")
                    self.provision_trusted()

        self._renew_mon = threading.Thread(target=monitor, name="optibubble-renew",
                                           daemon=True)
        self._renew_mon.start()

    def stop_server(self) -> None:
        if self._https_server is not None:
            self._https_server.shutdown()
            self._https_server = None
        if self._server is not None:
            self._server.shutdown()
            self._server = None
            self.emit("server_stopped")

    @property
    def https_running(self) -> bool:
        return self._https_server is not None

    def cert_url(self, ip: Optional[str] = None) -> str:
        ip = ip or self.lan_ips()[0]
        return f"http://{ip}:{self.settings.port}/cert"

    def https_url(self, ip: Optional[str] = None) -> str:
        if not self.test:
            return ""
        host = self._https_host or ip or self.lan_ips()[0]
        return (f"https://{host}:{self.settings.https_port}/scan/"
                f"{self.test.session_token}")

    @property
    def server_running(self) -> bool:
        return self._server is not None

    @property
    def server_error(self) -> str:
        return self._server_error

    # ------------------------------------------------------------------ uploads
    def accept_upload(self, token: str, data: bytes) -> Tuple[Optional[str], Optional[dict]]:
        """Called by the HTTP layer. Returns (receipt_id, error)."""
        if not self.test or token != self.test.session_token:
            return None, {"code": "BAD_SESSION",
                          "message": "This scan link is no longer active.",
                          "hint": "Scan the QR code shown on the teacher's screen."}
        if len(data) > self.settings.max_upload_mb * 1024 * 1024:
            return None, {"code": "TOO_LARGE",
                          "message": "Photo is larger than the upload limit.",
                          "hint": "Try again, or lower quality in Settings."}
        rid = uuid.uuid4().hex[:12]
        with self._receipt_lock:
            if len(self.receipts) > 200:          # bound memory on long sessions
                for stale in list(self.receipts)[: len(self.receipts) - 200]:
                    self.receipts.pop(stale, None)
            self.receipts[rid] = {"status": "queued", "result": None, "error": None}
        self.stats["sheets_received"] += 1
        # Snapshot the active test + layout + storage root NOW. If the teacher
        # opens another test while this sheet is queued/processing, the worker
        # must grade against the session it was scanned for, not the current one.
        self._pool.submit(self._process, rid, data,
                          self.test, self.layout,
                          self.storage.test_root(self.test) if self.test else None)
        return rid, None

    def get_receipt(self, rid: str) -> dict:
        with self._receipt_lock:
            return dict(self.receipts.get(rid) or {"status": "unknown"})

    def _process(self, rid: str, data: bytes, test=None, layout=None,
                 test_root=None) -> None:
        # `test` / `layout` / `test_root` are the snapshot captured at upload
        # time by accept_upload; fall back to the live state for callers that
        # submit directly (e.g. the self-test's psychometrics loop).
        test = test or self.test
        layout = layout or self.layout
        if test_root is None:
            test_root = self.storage.test_root(test) if test else None
        with self._receipt_lock:
            self.receipts.setdefault(rid, {"status": "queued", "result": None,
                                           "error": None})
            self.receipts[rid]["status"] = "processing"

        def fail(code: str, message: str, hint: str = "") -> None:
            self.stats["rejected"] += 1
            with self._receipt_lock:
                self.receipts[rid].update(status="error",
                                          error={"code": code, "message": message,
                                                 "hint": hint})
            self.emit("sheet_rejected", code=code, message=message)

        if not test or not layout or not test_root:
            fail("NO_TEST", "No active test on the desktop side.")
            return
        try:
            result = grade_photo(data, layout, test, self.settings, test_root,
                                 debug_dir=test_root / "debug")
        except OMRReject as e:
            fail(e.code, e.message, e.hint)
            return
        except Exception as e:  # pragma: no cover
            fail("ENGINE_ERROR", "Processing failed on the desktop.", str(e))
            return

        sheet_path = self.storage.save_sheet_image(test, data, result.sheet_id)
        rel_image = str(sheet_path.relative_to(test_root))

        if result.status == "auto":
            self.storage.append_result(test, result, rel_image,
                                       master=self.settings.master_csv)
            self.stats["auto_graded"] += 1
        else:
            self.storage.queue_for_review(test, result, rel_image)
            self.stats["flagged"] += 1

        sid = result.student_id.strip("?")
        if sid and sid in self._seen_ids:
            self.log(f"⚠ duplicate: student {sid} already submitted a sheet "
                     f"({int(time.time() - self._seen_ids[sid])}s ago)", "warn")
        if sid:
            self._seen_ids[sid] = time.time()

        with self._receipt_lock:
            self.receipts[rid].update(status="done", result=result.summary())

        # Desktop camera frames are graded via accept_upload with a synthetic
        # session; guard the event/emit against a test that was switched away.
        self.emit("sheet_graded" if result.status == "auto" else "sheet_flagged",
                  result=result, image=rel_image)

    # ------------------------------------------------------------------ review
    def resolve_flagged(self, sheet_id: str, answers: Optional[Dict[int, Optional[str]]],
                        student_id: Optional[str]) -> bool:
        """Apply human overrides to a flagged sheet and finalise it."""
        if not self.test:
            return False
        for item in self.storage.pending_reviews(self.test):
            res = result_from_json(item["result"])
            if res.sheet_id != sheet_id:
                continue
            if answers is not None:
                for q, a in answers.items():
                    res.answers[int(q)] = a
            if student_id is not None:
                res.student_id = student_id
            res.flags = []
            # Honour per-question weights and partial-credit fractions when a
            # human confirms a flagged sheet. Previously this rescored as
            # 1 point per correct answer, corrupting Total_Score / Percent for
            # any weighted test (e.g. "5:2, 9-12:3").
            total = 0.0
            for q in res.answers:
                a = res.answers[q]
                if a and self.test.answer_key.get(int(q)) == a:
                    total += self.test.weight_for(int(q))          # confirmed correct
                elif q in res.partials:
                    total += self.test.partial_multi_credit * self.test.weight_for(int(q))
                # otherwise wrong / blank → 0
            res.score = total
            self.storage.resolve_review(self.test, sheet_id, res, item.get("source_image", ""))
            self.emit("review_resolved", sheet_id=sheet_id, score=res.score,
                      student_id=res.student_id)
            return True
        return False

    def discard_flagged(self, sheet_id: str) -> bool:
        if not self.test:
            return False
        p = self.storage.test_root(self.test) / "review" / "pending" / f"{sheet_id}.json"
        if p.exists():
            p.unlink()
            self.emit("review_discarded", sheet_id=sheet_id)
            return True
        return False

    # ------------------------------------------------------------------ misc
    def save_settings(self) -> None:
        self.settings.clamp()
        self.settings.save(settings_path(self.data_dir))
        self.emit("settings_saved")

    # -------------------------------------------------- desktop USB camera
    def camera_devices(self) -> List[dict]:
        """Probe the first few video device indices (quick, read-only)."""
        import cv2 as _cv
        out = []
        for idx in range(4):
            cap = _cv.VideoCapture(idx)
            ok = cap.isOpened()
            w = int(cap.get(_cv.CAP_PROP_FRAME_WIDTH)) if ok else 0
            cap.release()
            if ok:
                out.append({"index": idx, "label": f"Camera {idx}",
                            "width": w})
        return out

    def camera_start(self, index: int = 0, synthetic: Optional[str] = None
                     ) -> Tuple[bool, str]:
        ok, msg = self.camera.start(index, synthetic)
        if ok:
            self.log(f"Camera live — {msg} (desktop scanning station)")
        else:
            self.log(f"Camera failed: {msg}", "warn")
        return ok, msg

    def camera_stop(self) -> None:
        self.camera.stop()
        self.log("Camera stopped")

    def camera_frame_jpeg(self) -> Optional[bytes]:
        return self.camera.frame_jpeg()

    # -------------------------------------------------- WebRTC mirror slots
    def mirror_post(self, slot: str, payload) -> None:
        with self._mirror_lock:
            self._mirror[slot] = ({"payload": payload, "ts": time.time()}
                                  if payload is not None else None)

    def mirror_get(self, slot: str) -> Optional[dict]:
        with self._mirror_lock:
            item = self._mirror.get(slot)
        if not item:
            return None
        if time.time() - item["ts"] > 300:      # stale signaling → drop
            self.mirror_post(slot, None)
            return None
        return item

    def shutdown(self) -> None:
        self.stop_server()
        try:
            self.camera.stop()
        except Exception:
            pass
        self._pool.shutdown(wait=False, cancel_futures=True)
