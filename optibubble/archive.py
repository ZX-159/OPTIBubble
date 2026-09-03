"""
Encrypted local archiving — one-button test backups.

Formats ``.optibubble``::

    v1 (encrypted):  b"OBAR1" + salt(16) + nonce(12) + AES-256-GCM(zip(...))
    v2 (plain):      b"OBAR2" + zip(...)            — no password requested

* the whole test folder (sheet PDF, answer key, photos, crops, results.csv,
  test.json) is zipped, then sealed with a key derived from the teacher's
  password via PBKDF2-HMAC-SHA256 (200 000 iterations);
* standard building blocks only — decryptable by this app on any OS;
* wrong password simply fails the GCM tag check.

Also handles plain ``.zip`` archives (imported as-is, no password).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Tuple

MAGIC = b"OBAR1"
MAGIC_V2 = b"OBAR2"
KDF_ITERS = 200_000


def _derive(password: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=KDF_ITERS).derive(password.encode())


def create_archive(test_root: Path, password: str = "") -> bytes:
    """Zip a test folder into .optibubble bytes.

    With a password → v1 encrypted container (AES-256-GCM).
    Without → v2 plain container (bytes 5:7] == b"OBAR2" + raw zip).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        top = Path(test_root).name          # self-describing: <test_id>/…
        for p in sorted(Path(test_root).rglob("*")):
            if p.is_file():
                z.write(p, f"{top}/{p.relative_to(test_root).as_posix()}")
    if password:
        import secrets
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
        key = _derive(password, salt)
        sealed = AESGCM(key).encrypt(nonce, buf.getvalue(), MAGIC)
        return MAGIC + salt + nonce + sealed
    return MAGIC_V2 + buf.getvalue()


def restore_archive(data: bytes, password: str,
                    tests_dir: Path) -> Tuple[str, int]:
    """Decrypt + extract an archive into <tests_dir>. Returns (test_id, nfiles).

    Raises ValueError with a friendly message on wrong password/corruption
    or a name collision.
    """
    if data[:5] == MAGIC_V2:
        raw = data[5:]
        if raw[:2] != b"PK":
            raise ValueError("Damaged archive (bad zip header).")
    elif data[:5] == MAGIC:
        salt, nonce, sealed = data[5:21], data[21:33], data[33:]
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = _derive(password or "", salt)
        try:
            raw = AESGCM(key).decrypt(nonce, sealed, MAGIC)
        except Exception:
            raise ValueError("Wrong password or damaged archive.")
    else:
        if data[:2] != b"PK":
            raise ValueError("Not an OPTIBubble archive (or zip).")
        raw = data
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    if not names:
        raise ValueError("Archive is empty.")
    # the test id is the directory that contains test.json (not the
    # alphabetically-first entry, which may be review/ or sheets/)
    test_id = next((n.split("/")[0] for n in names
                    if n.endswith("/test.json")), names[0].split("/")[0])
    if (tests_dir / test_id).exists():
        raise ValueError(f"A test called “{test_id}” already exists — "
                         "delete or rename it first.")
    n = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        dest = (tests_dir / info.filename).resolve()
        if not str(dest).startswith(str(tests_dir.resolve())):
            raise ValueError("Archive contains unsafe paths.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zf.read(info))
        n += 1
    return test_id, n
