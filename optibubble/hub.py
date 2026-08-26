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
from .sheet_generator import generate_sheet_pdf, render_pdf_preview
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
        self._server_error: str = ""

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
        self.test = test
        self.emit("test_created", test_id=test.test_id, title=test.title)

    def pdf_path(self) -> Optional[Path]:
        if not self.test:
            return None
        p = self.storage.test_root(self.test) / "sheet.pdf"
        return p if p.exists() else None

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
        ips: List[str] = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.3)
            s.connect(("8.8.8.8", 80))     # no packets actually sent
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None,
                                           socket.AF_INET):
                ip = info[4][0]
                if ip not in ips and not ip.startswith("127."):
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
            self._server = make_server(self.settings.host, self.settings.port, app,
                                       threaded=True)
            self._server_thread = threading.Thread(target=self._server.serve_forever,
                                                   name="optibubble-server", daemon=True)
            self._server_thread.start()
            self.emit("server_started", url=self.magic_url())
            return True
        except OSError as e:
            self._server = None
            self._server_error = str(e)
            self.emit("server_error", error=str(e))
            return False

    def stop_server(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None
            self.emit("server_stopped")

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
        self._pool.submit(self._process, rid, data)
        return rid, None

    def get_receipt(self, rid: str) -> dict:
        with self._receipt_lock:
            return dict(self.receipts.get(rid) or {"status": "unknown"})

    def _process(self, rid: str, data: bytes) -> None:
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

        if not self.test or not self.layout:
            fail("NO_TEST", "No active test on the desktop side.")
            return
        try:
            result = grade_photo(data, self.layout, self.test, self.settings,
                                 self.storage.test_root(self.test),
                                 debug_dir=self.storage.test_root(self.test) / "debug")
        except OMRReject as e:
            fail(e.code, e.message, e.hint)
            return
        except Exception as e:  # pragma: no cover
            fail("ENGINE_ERROR", "Processing failed on the desktop.", str(e))
            return

        sheet_path = self.storage.save_sheet_image(self.test, data, result.sheet_id)
        rel_image = str(sheet_path.relative_to(self.storage.test_root(self.test)))

        if result.status == "auto":
            self.storage.append_result(self.test, result, rel_image,
                                       master=self.settings.master_csv)
            self.stats["auto_graded"] += 1
        else:
            self.storage.queue_for_review(self.test, result, rel_image)
            self.stats["flagged"] += 1

        sid = result.student_id.strip("?")
        if sid and sid in self._seen_ids:
            self.log(f"⚠ duplicate: student {sid} already submitted a sheet "
                     f"({int(time.time() - self._seen_ids[sid])}s ago)", "warn")
        if sid:
            self._seen_ids[sid] = time.time()

        with self._receipt_lock:
            self.receipts[rid].update(status="done", result=result.summary())

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
            res.score = sum(1 for q, a in res.answers.items()
                            if a and self.test.answer_key.get(int(q)) == a)
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

    def shutdown(self) -> None:
        self.stop_server()
        self._pool.shutdown(wait=False, cancel_futures=True)
