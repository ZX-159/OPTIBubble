"""
Local data storage: session folders, the review queue and CSV export.

Layout on disk (default data root ``~/OPTIBubbleData``)::

    ~/OPTIBubbleData/
      settings.json
      master_results.csv            ← optional global export
      tests/
        T123456/                    ← one folder per test session
          test.json                 ← TestConfig + sheet layout (geometry)
          sheet.pdf                 ← printable answer sheet
          sheets/                   ← every photo received from phones
          review/pending/           ← flagged sheets awaiting human review
          review/crops/             ← cropped PNGs of disputed bubbles
          results.csv               ← final results for this test
"""

from __future__ import annotations

import csv
import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import TestConfig, default_data_dir, tests_dir
from .layout import SheetLayout
from .omr_engine import Flag, GradeResult

CSV_COLUMNS = ["Timestamp", "Student_ID", "Test_ID", "Test_Title", "Total_Score",
               "Max_Score", "Percent", "Detailed_Answers_JSON", "Status",
               "Source_Image"]


class Storage:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "tests").mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._csv_cache: Dict[Path, tuple] = {}   # path → (mtime, size, rows)

    # ------------------------------------------------------------- caching
    def _cached_rows(self, csv_path: Path) -> List[dict]:
        """Read a results CSV, cached until the file actually changes."""
        if not csv_path.exists():
            return []
        try:
            st = csv_path.stat()
            key = (st.st_mtime_ns, st.st_size)
            hit = self._csv_cache.get(csv_path)
            if hit and hit[0] == key:
                return hit[1]
            with csv_path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self._csv_cache[csv_path] = (key, rows)
            return rows
        except Exception:
            return []

    # ------------------------------------------------------------- sessions
    def test_root(self, test: TestConfig) -> Path:
        return tests_dir(self.data_dir) / test.test_id

    def create_session(self, test: TestConfig) -> Path:
        root = self.test_root(test)
        for sub in ("sheets", "review/pending", "review/crops"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        test.created_at = test.created_at or time.strftime("%Y-%m-%d %H:%M:%S")
        self.save_test(test)
        return root

    def save_test(self, test: TestConfig, layout: Optional[SheetLayout] = None) -> None:
        root = self.test_root(test)
        root.mkdir(parents=True, exist_ok=True)
        payload = {"test": test.to_dict()}
        if layout is not None:
            payload["layout"] = layout.to_dict()
        (root / "test.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_test(self, test_id: str) -> Optional[dict]:
        p = tests_dir(self.data_dir) / test_id / "test.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_tests(self) -> List[dict]:
        out: List[dict] = []
        root = tests_dir(self.data_dir)
        if not root.exists():
            return out
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            data = self.load_test(d.name)
            if data:
                meta = data["test"]
                meta["graded"] = self._count_rows(d / "results.csv")
                out.append(meta)
        return out

    # ------------------------------------------------------------- results
    def _count_rows(self, csv_path: Path) -> int:
        return len(self._cached_rows(csv_path))

    def result_to_row(self, test: TestConfig, r: GradeResult,
                      source_image: str = "") -> dict:
        detail = {
            "answers": {str(q): a for q, a in r.answers.items()},
            "correct": {str(q): c for q, c in r.correct.items()},
            "flags": [{"q": f.q, "digit": f.digit, "kind": f.kind, "guess": f.guess}
                      for f in r.flags],
            "confidence": round(r.confidence, 4),
            "sheet_id": r.sheet_id,
            "reviewed": r.status == "verified",
        }
        pct = round(100.0 * r.score / r.max_score, 1) if r.max_score else 0.0
        return {
            "Timestamp": r.ts,
            "Student_ID": r.student_id or "",
            "Test_ID": test.test_id,
            "Test_Title": test.title,
            "Total_Score": r.score,
            "Max_Score": r.max_score,
            "Percent": pct,
            "Detailed_Answers_JSON": json.dumps(detail, ensure_ascii=False),
            "Status": "Verified" if r.status in ("auto", "verified") else "Flagged",
            "Source_Image": source_image,
        }

    def append_result(self, test: TestConfig, r: GradeResult,
                      source_image: str = "", master: bool = True) -> Path:
        row = self.result_to_row(test, r, source_image)
        csv_path = self.test_root(test) / "results.csv"
        with self._lock:
            new_file = not csv_path.exists()
            with csv_path.open("a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                if new_file:
                    w.writeheader()
                w.writerow(row)
            if master:
                master_path = self.data_dir / "master_results.csv"
                new_master = not master_path.exists()
                with master_path.open("a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                    if new_master:
                        w.writeheader()
                    w.writerow(row)
        return csv_path

    def read_results(self, test: TestConfig) -> List[dict]:
        return self._cached_rows(self.test_root(test) / "results.csv")

    # ------------------------------------------------------------- review
    def queue_for_review(self, test: TestConfig, r: GradeResult,
                         source_image: str = "") -> Path:
        pending = self.test_root(test) / "review" / "pending" / f"{r.sheet_id}.json"
        payload = {"test_id": test.test_id, "source_image": source_image,
                   "result": _result_to_json(r)}
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return pending

    def pending_reviews(self, test: TestConfig) -> List[dict]:
        d = self.test_root(test) / "review" / "pending"
        if not d.exists():
            return []
        out = []
        for p in sorted(d.glob("*.json")):
            try:
                item = json.loads(p.read_text(encoding="utf-8"))
                item["_file"] = str(p)
                out.append(item)
            except Exception:
                continue
        return out

    def resolve_review(self, test: TestConfig, sheet_id: str,
                       resolved: GradeResult, source_image: str = "") -> None:
        """Write verified result to CSV and drop the pending item."""
        resolved.status = "verified"
        self.append_result(test, resolved, source_image, master=True)
        p = self.test_root(test) / "review" / "pending" / f"{sheet_id}.json"
        if p.exists():
            p.unlink()

    def save_sheet_image(self, test: TestConfig, data: bytes,
                         sheet_id: str) -> Path:
        d = self.test_root(test) / "sheets"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{sheet_id}.jpg"
        path.write_bytes(data)
        return path


def _result_to_json(r: GradeResult) -> dict:
    return {
        "sheet_id": r.sheet_id, "ts": r.ts, "page": r.page,
        "student_id": r.student_id,
        "answers": {str(k): v for k, v in r.answers.items()},
        "correct": {str(k): v for k, v in r.correct.items()},
        "score": r.score, "max_score": r.max_score,
        "confidence": round(r.confidence, 4),
        "status": r.status,
        "flags": [{"kind": f.kind, "q": f.q, "digit": f.digit, "guess": f.guess,
                   "message": f.message, "crop": f.crop} for f in r.flags],
        "duration_ms": r.duration_ms,
    }


def result_from_json(d: dict) -> GradeResult:
    return GradeResult(
        sheet_id=d.get("sheet_id", ""), ts=d.get("ts", ""),
        page=d.get("page", 1), student_id=d.get("student_id", ""),
        answers={int(k): v for k, v in d.get("answers", {}).items()},
        correct={int(k): v for k, v in d.get("correct", {}).items()},
        score=d.get("score", 0), max_score=d.get("max_score", 0),
        confidence=d.get("confidence", 1.0),
        flags=[Flag(**f) for f in d.get("flags", [])],
        status=d.get("status", "auto"),
        duration_ms=d.get("duration_ms", 0))
