#!/usr/bin/env python3
"""
Version sync — one source of truth, every manifest.

    python tools/sync_version.py            # propagate the current version
    python tools/sync_version.py 1.5.0      # set + propagate

Reads/writes optibubble/__init__.py and keeps src-tauri/tauri.conf.json,
src-tauri/Cargo.toml and src-tauri/Cargo.lock in sync. The self-test asserts
they match, and CI runs the self-test — versions can never drift again.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "optibubble" / "__init__.py"


def read_version() -> str:
    return re.search(r'__version__ = "([^"]+)"', INIT.read_text()).group(1)


def write_version(v: str) -> None:
    INIT.write_text(re.sub(r'__version__ = "[^"]+"',
                           f'__version__ = "{v}"', INIT.read_text()))


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg:
        if not re.fullmatch(r"\d+\.\d+\.\d+", arg):
            raise SystemExit("version must be major.minor.patch, e.g. 1.5.0")
        write_version(arg)
    v = read_version()

    p = ROOT / "src-tauri" / "tauri.conf.json"
    conf = json.loads(p.read_text())
    conf["version"] = v
    p.write_text(json.dumps(conf, indent=2) + "\n")

    p = ROOT / "src-tauri" / "Cargo.toml"
    toml = p.read_text()
    toml = re.sub(r'^version = "[^"]+"', f'version = "{v}"', toml,
                  count=1, flags=re.M)
    p.write_text(toml)

    p = ROOT / "src-tauri" / "Cargo.lock"
    if p.exists():
        lock = p.read_text()
        lock = re.sub(r'(name = "optibubble"\nversion = ")[^"]+"',
                      r"\g<1>" + v + '"', lock)
        p.write_text(lock)
    print(f"version synced everywhere: {v}")


if __name__ == "__main__":
    main()
