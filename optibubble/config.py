"""
Configuration, advanced settings and persistence for OPTIBubble.

Everything the user can fine-tune lives in :class:`AdvancedSettings`.
A :class:`TestConfig` describes one MCQ test (questions, options, key).
Both are plain dataclasses that serialise to JSON so sessions can be
reloaded later without a database.
"""

from __future__ import annotations

import json
import random
import re
import string
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
FONTS_DIR = BASE_DIR / "fonts"

FONT_OPTI = "OPTIBubbleDoubleBold"           # logo wordmark font
FONT_OPEN_SANS = "OpenSans"                   # body font family (registered variants)

LETTERS = "ABCDEFGHIJ"


# ----------------------------------------------------------------------------
# Advanced / fine-tune settings
# ----------------------------------------------------------------------------
@dataclass
class AdvancedSettings:
    """Fine-tuning knobs for the OMR engine, camera bridge and server.

    The defaults are deliberately conservative so that black / blue ballpoint
    pens and dark pencils are recognised out of the box.  Every value can be
    adjusted from the desktop GUI (*Settings → OMR Engine / Camera / Server*).
    """

    # --- OMR engine (thresholds are GRID-RELATIVE: 0 = empty sibling bubble,
    #     1 = printed ink — invariant to exposure and local shadows) -----------
    warp_width_px: int = 1600          # width of the flattened (warped) page
    dark_threshold_offset: int = 0     # -60..60, shift binarisation threshold
    t_blank: float = 0.14              # below → considered an empty bubble
    t_fill: float = 0.34               # above → considered a filled bubble
    faint_upper: float = 0.65          # fill between t_fill..this → "faint" flag
    multi_ratio: float = 0.62          # 2nd/top above this → "multi" flag
    inner_sample: float = 0.62         # fraction of bubble radius sampled
    min_photo_dim_px: int = 700        # reject tiny/low-res photos
    auto_accept_blank: bool = False    # grade blank as wrong without review
    save_debug_warp: bool = False      # keep flattened page images on disk

    # --- camera bridge / mobile ---------------------------------------------
    jpeg_quality: int = 92             # mobile → PC upload quality
    target_width_px: int = 2048        # requested capture resolution

    # --- local server -------------------------------------------------------
    host: str = "0.0.0.0"              # bind all interfaces (LAN reachable)
    port: int = 5000
    https_port: int = 5443             # HTTPS bridge (live mobile camera)
    enable_https: bool = True
    max_upload_mb: int = 30

    # --- HTTPS mode for the mobile camera ------------------------------------
    # "local"       → built-in CA (offline; students install cert via code A)
    # "letsencrypt" → publicly-trusted cert via DNS-01 + DuckDNS (zero student
    #                 setup; needs internet once at provisioning time)
    https_mode: str = "local"
    acme_domain: str = ""              # e.g. myclass.duckdns.org
    duckdns_token: str = ""            # from duckdns.org
    acme_email: str = ""               # for expiry notices

    # --- behaviour ----------------------------------------------------------
    master_csv: bool = True            # also append to a master results file
    theme: str = "dark"                # dark | light
    color_mode_accent: str = "#3B82F6"

    # ------------------------------------------------------------------
    def clamp(self) -> "AdvancedSettings":
        self.warp_width_px = int(max(900, min(2600, self.warp_width_px)))
        self.dark_threshold_offset = int(max(-60, min(60, self.dark_threshold_offset)))
        self.t_blank = float(min(max(self.t_blank, 0.03), 0.30))
        self.t_fill = float(min(max(self.t_fill, self.t_blank + 0.04), 0.60))
        self.faint_upper = float(min(max(self.faint_upper, self.t_fill + 0.02), 0.85))
        self.multi_ratio = float(min(max(self.multi_ratio, 0.30), 0.95))
        self.inner_sample = float(min(max(self.inner_sample, 0.40), 0.85))
        self.min_photo_dim_px = int(max(320, min(4000, self.min_photo_dim_px)))
        self.jpeg_quality = int(max(60, min(100, self.jpeg_quality)))
        self.target_width_px = int(max(1280, min(4096, self.target_width_px)))
        self.port = int(max(1024, min(65535, self.port)))
        self.https_port = int(max(1024, min(65535, self.https_port)))
        self.max_upload_mb = int(max(5, min(100, self.max_upload_mb)))
        self.theme = self.theme if self.theme in ("dark", "light") else "dark"
        self.https_mode = self.https_mode if self.https_mode in ("local",
                                                                "letsencrypt") else "local"
        self.acme_domain = self.acme_domain.strip().lower()
        self.duckdns_token = self.duckdns_token.strip()
        self.acme_email = self.acme_email.strip()
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "AdvancedSettings":
        s = cls()
        if isinstance(d, dict):
            for k, v in d.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        return s.clamp()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "AdvancedSettings":
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
        return cls()


# ----------------------------------------------------------------------------
# Test configuration
# ----------------------------------------------------------------------------
@dataclass
class TestConfig:
    """A single MCQ test definition + its answer key + sheet design."""

    title: str = "Untitled Test"
    subject: str = "General"
    num_questions: int = 20
    options_per_question: int = 4                 # 2..5  (A-D, A-E …)
    answer_key: Dict[int, str] = field(default_factory=dict)   # {1: "A", ...}
    student_id_digits: int = 7                    # 0 → no student ID grid
    page_size: str = "a4"                         # a4 | letter
    test_id: str = ""                             # short public id
    session_token: str = ""                       # secret for the magic link
    created_at: str = ""

    # --- sheet design (editable per test, never touches the answer area) ---
    sheet_instructions: str = ""                  # custom instruction lines;
                                                  # "" → default helper text
    header_font_scale: float = 1.0                # 0.8 .. 1.4 header text scale
    logo_position: str = "left"                   # left | right (wordmark side)
    write_in_fields: str = "Name,Class,Date"       # handwritten fields; the
                                                  # scanner ignores them entirely

    # --- scoring ------------------------------------------------------------
    default_points: float = 1.0                   # points per question
    weights: Dict[int, float] = field(default_factory=dict)  # per-question pts
    partial_multi_credit: float = 0.0             # 0..1 — fraction of the
                                                  # question's points awarded
                                                  # automatically when a double
                                                  # mark still contains the key

    # ------------------------------------------------------------------
    def validate(self) -> List[str]:
        errs: List[str] = []
        if not self.title or not self.title.strip():
            errs.append("Test title is required.")
        self.title = self.title.strip()[:80]
        self.subject = (self.subject or "General").strip()[:80]
        if not (2 <= self.num_questions <= 102):
            errs.append("Number of questions must be between 2 and 102.")
        if not (2 <= self.options_per_question <= 5):
            errs.append("Options per question must be between 2 and 5.")
        if self.page_size not in ("a4", "letter"):
            errs.append("Page size must be 'a4' or 'letter'.")
        if not (0 <= self.student_id_digits <= 10):
            errs.append("Student ID digits must be between 0 and 10.")
        if not (0.8 <= self.header_font_scale <= 1.4):
            errs.append("Header text size must be between 80% and 140%.")
        self.header_font_scale = float(min(max(self.header_font_scale, 0.8), 1.4))
        if self.logo_position not in ("left", "right"):
            self.logo_position = "left"
        self.sheet_instructions = (self.sheet_instructions or "").strip()[:240]
        self.write_in_fields = self.parse_write_in_fields_text(self.write_in_fields)
        self.default_points = float(min(max(self.default_points or 1.0, 0.1), 100.0))
        self.partial_multi_credit = float(min(
            max(self.partial_multi_credit or 0.0, 0.0), 1.0))
        self.weights = {int(q): max(0.0, float(v))
                        for q, v in (self.weights or {}).items()}
        bad = {q: a for q, a in self.answer_key.items()
               if a not in LETTERS[: self.options_per_question]}
        if bad:
            errs.append(f"Answer key has invalid entries (allowed: "
                        f"A-{LETTERS[self.options_per_question - 1]}).")
        return errs

    WRITE_IN_MAX = 6

    @staticmethod
    def parse_weights_text(text: str) -> Dict[int, float]:
        """Parse “5:2, 9-12:3, 15:2.5” into {q: points}."""
        import re as _re
        out: Dict[int, float] = {}
        for tok in (text or "").replace(";", ",").split(","):
            tok = tok.strip().rstrip(".")
            if not tok:
                continue
            m = _re.fullmatch(r"(\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*:\s*([0-9]*\.?[0-9]+)", tok)
            if not m:
                raise ValueError(f"Bad points entry “{tok}” — use e.g. 5:2 or 9-12:3")
            a = int(m.group(1)); b = int(m.group(2) or a)
            pts = float(m.group(3))
            for q in range(min(a, b), max(a, b) + 1):
                out[q] = pts
        return out

    def weight_for(self, qn: int) -> float:
        return float(self.weights.get(qn, self.default_points))

    def parse_write_in_fields_text(self, text: str) -> str:
        """Normalise a comma/space separated label list → canonical CSV string."""
        parts = [p.strip()[:14] for p in (text or "").replace(";", ",").split(",")
                 if p.strip()]
        return ",".join(parts[: self.WRITE_IN_MAX])

    def write_in_field_list(self) -> List[str]:
        return [p for p in (self.write_in_fields or "").split(",") if p.strip()]

    # ------------------------------------------------------------------
    @property
    def max_letters(self) -> str:
        return LETTERS[: self.options_per_question]

    def ensure_ids(self) -> None:
        if not self.test_id:
            self.test_id = "T" + "".join(random.choices(string.digits, k=6))
        if not self.session_token:
            alphabet = string.ascii_lowercase + string.digits
            self.session_token = "".join(random.choices(alphabet, k=10))

    # ------------------------------------------------------------------
    # Answer key helpers
    # ------------------------------------------------------------------
    def parse_key_text(self, text: str) -> int:
        """Populate the key from free text such as ``1:A 2:C`` or ``ACBD...``.

        Letters are validated against *this test's* ``options_per_question``
        (not a hard-coded ``[A-J]``), so ``1:A 2:F 3:C`` on a 4-option test
        correctly skips the invalid ``F``.  The number of entries dropped
        because they were out of range / invalid is stored on
        ``self.last_key_dropped`` so callers can warn instead of silently
        leaving a gap in the key.

        Returns the number of parsed entries.  Raises ValueError on garbage.
        """
        text = (text or "").strip().upper()
        self.last_key_dropped = 0
        if not text:
            self.answer_key = {}
            return 0
        allowed = "[" + self.max_letters + "]"
        kv = re.findall(r"(\d{1,3})\s*[:.\-]\s*(" + allowed + ")", text)
        if kv and len(kv) >= 2:
            new = {}
            for q, a in kv:
                qi = int(q)
                if 1 <= qi <= self.num_questions and a in self.max_letters:
                    new[qi] = a
            self.answer_key = new
            # count entries the text carried but we couldn't apply
            carried = len(re.findall(r"(\d{1,3})\s*[:.\-]\s*([A-Z])", text))
            self.last_key_dropped = max(0, carried - len(new))
            return len(new)
        # compact form: "ABCDAACB..."
        compact = re.sub(r"[^" + self.max_letters + "]", "", text)
        if compact:
            self.answer_key = {i + 1: a for i, a in enumerate(compact[: self.num_questions])
                               if a in self.max_letters}
            self.last_key_dropped = len(re.sub(r"[^A-Z]", "", text)) - len(self.answer_key)
            return len(self.answer_key)
        raise ValueError("Could not parse the answer key text.")

    def key_to_text(self) -> str:
        return " ".join(f"{q}:{a}" for q, a in sorted(self.answer_key.items()))

    def randomize_key(self) -> None:
        self.answer_key = {i + 1: random.choice(self.max_letters)
                           for i in range(self.num_questions)}

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["answer_key"] = {str(k): v for k, v in self.answer_key.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TestConfig":
        t = cls()
        for k in ("title", "subject", "num_questions", "options_per_question",
                  "student_id_digits", "page_size", "test_id", "session_token",
                  "created_at", "sheet_instructions", "logo_position",
                  "write_in_fields", "default_points", "partial_multi_credit"):
            if k in d:
                setattr(t, k, d[k])
        t.header_font_scale = float(d.get("header_font_scale", 1.0) or 1.0)
        t.default_points = float(d.get("default_points", 1.0) or 1.0)
        t.partial_multi_credit = float(d.get("partial_multi_credit", 0.0) or 0.0)
        t.weights = {int(q): float(v) for q, v in (d.get("weights") or {}).items()}
        t.answer_key = {int(q): a for q, a in (d.get("answer_key") or {}).items()}
        return t


# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
def default_data_dir() -> Path:
    """User data root.

    Deliberately *not* ``~/OPTIBubble`` — that is the natural clone location
    of this repository, and runtime data must never mix with source files.
    """
    return Path.home() / "OPTIBubbleData"


def settings_path(data_dir: Path) -> Path:
    return data_dir / "settings.json"


def tests_dir(data_dir: Path) -> Path:
    return data_dir / "tests"
