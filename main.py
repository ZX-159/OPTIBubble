#!/usr/bin/env python3
"""
OPTIBubble — launcher.

    python main.py                 start the desktop app (opens your browser;
                                   the same UI runs inside the Tauri shell)
    python main.py --no-browser    start without opening a browser
    python main.py --selftest      run the end-to-end engine/server test suite
    python main.py --demo          create a demo test session
    python main.py --serve T1234   headless: open a saved test & start serving
    python main.py --pdf T1234     regenerate the sheet PDF for a saved test
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from optibubble import __version__  # noqa: E402

APP_PORT_NOTE = "Tauri mode: the wrapper (src-tauri) starts this same server and " \
                "loads it in a native window — see README → Native app (Tauri)."


def _open_browser(url: str) -> None:
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()


def _write_port_file(path, port: int) -> None:
    """Pub/record the port actually bound so the Tauri shell can learn it."""
    if not path:
        return
    try:
        Path(path).write_text(str(int(port)), encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(prog="OPTIBubble",
                                 description="Local OMR & mobile-bridge grading system")
    ap.add_argument("--version", action="version", version=f"OPTIBubble {__version__}")
    ap.add_argument("--selftest", action="store_true", help="run end-to-end tests")
    ap.add_argument("--demo", action="store_true", help="create a demo test session")
    ap.add_argument("--serve", metavar="TEST_ID", help="headless server for a saved test")
    ap.add_argument("--pdf", metavar="TEST_ID", help="regenerate sheet PDF for a test")
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    ap.add_argument("--port", type=int, default=None, help="override the server port")
    ap.add_argument("--data-dir", default=None, help="override the data directory")
    ap.add_argument("--port-file", default=None,
                    help="write the actual bound HTTP port here so an external "
                         "shell (e.g. the Tauri wrapper) can learn it when the "
                         "configured port was busy and the engine fell back")
    args = ap.parse_args()

    data_dir = Path(args.data_dir).expanduser() if args.data_dir else None

    if args.selftest:
        import selftest
        return selftest.main()

    from optibubble.config import TestConfig
    from optibubble.hub import Hub

    hub = Hub(data_dir=data_dir)
    if args.port:
        hub.settings.port = args.port
        hub.save_settings()

    if args.pdf:
        if not hub.open_test(args.pdf):
            print(f"No saved test '{args.pdf}' in {hub.data_dir}")
            return 1
        from optibubble.sheet_generator import generate_sheet_pdf
        p, _ = generate_sheet_pdf(hub.test, hub.storage.test_root(hub.test) / "sheet.pdf",
                                  hub.layout)
        print("Sheet written to", p)
        return 0

    if args.serve:
        if not hub.open_test(args.serve):
            print(f"No saved test '{args.serve}' in {hub.data_dir}")
            return 1
        if not hub.start_server():
            print("Could not start server:", hub.server_error)
            return 1
        _write_port_file(args.port_file, hub.settings.port)
        print(f"OPTIBubble server running → {hub.magic_url()}")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            hub.shutdown()
        return 0

    if args.demo:
        cfg = TestConfig(title="Demo Test — Try It Out", subject="Demo",
                         num_questions=10, options_per_question=4, student_id_digits=7)
        cfg.ensure_ids()
        cfg.randomize_key()
        hub.create_test(cfg, generate_pdf=True)
        print("Demo test created:", cfg.test_id)
        print("Data folder:", hub.data_dir)
        print("Answer key  :", cfg.key_to_text())
        print("Sheet PDF   :", hub.pdf_path())
        print("\nStart the app with:  python main.py   (it will open the demo automatically)")
        return 0

    # default → desktop web app (browser or Tauri webview)
    if not hub.test:
        tests = hub.storage.list_tests()
        if tests:
            hub.open_test(tests[0]["test_id"])
    if not hub.start_server():
        print("Could not start the app server:", hub.server_error)
        return 1
    _write_port_file(args.port_file, hub.settings.port)
    url = f"http://127.0.0.1:{hub.settings.port}/"
    print(f"\n  OPTIBubble {__version__} running → {url}")
    print("  Press Ctrl+C to quit.")
    if not args.no_browser:
        _open_browser(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nbye 👋")
        hub.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
