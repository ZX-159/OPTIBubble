"""
Desktop video capture — USB document cameras & webcams as scanning stations.

A background thread reads frames from ``cv2.VideoCapture`` so the GUI never
blocks; the newest frame is kept for preview (``/api/camera/frame.jpg``) and
for one-click grading through the exact same pipeline as phone photos.

A **synthetic source** (renders a sheet image with slight hand jitter) exists
for tests and demos on machines without a camera.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np


class CameraError(RuntimeError):
    pass


class _Synthetic:
    """Streams a sheet image with gentle jitter — tests/demos without hardware."""

    def __init__(self, image_path: str):
        img = cv2.imread(image_path)
        if img is None:
            raise CameraError(f"synthetic source image not found: {image_path}")
        self.sheet = img
        self.t = 0.0

    def read(self) -> Optional[np.ndarray]:
        self.t += 0.09
        H, W = 720, 960
        frame = np.full((H, W, 3), (98, 104, 112), np.uint8)
        sh, sw = self.sheet.shape[:2]
        scale = min((W - 120) / sw, (H - 100) / sh)
        nw, nh = int(sw * scale), int(sh * scale)
        sheet = cv2.resize(self.sheet, (nw, nh))
        import math
        jx = int(8 * math.sin(self.t)) + 60
        jy = int(6 * math.cos(self.t * 1.3)) + 50
        frame[jy:jy + nh, jx:jx + nw] = sheet
        time.sleep(0.08)
        return True, frame

    def release(self):
        pass


class CameraWorker:
    def __init__(self):
        self._lock = threading.Lock()
        self._on_lost = None
        self._source = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._frame: Optional[np.ndarray] = None
        self.label = ""

    # ------------------------------------------------------------------ life
    def start(self, index: int = 0, synthetic: Optional[str] = None,
              on_lost=None) -> Tuple[bool, str]:
        self._on_lost = on_lost
        self.stop()
        try:
            if synthetic:
                self._source = _Synthetic(synthetic)
                self.label = f"synthetic:{Path(synthetic).name}"
            else:
                cap = cv2.VideoCapture(int(index))
                if not cap.isOpened():
                    cap.release()
                    return False, (f"camera {index} not found — plug it in and "
                                   "try another index")
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 2592)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1944)
                self._source = cap
                self.label = f"camera {index}"
        except Exception as e:
            return False, str(e)[:120]
        self._running = True
        self._thread = threading.Thread(target=self._loop,
                                        name="optibubble-camera", daemon=True)
        self._thread.start()
        return True, self.label

    def stop(self) -> None:
        self._running = False
        with self._lock:
            if self._source is not None:
                self._source.release()
                self._source = None
            self._frame = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self.label = ""
        self._on_lost = None

    @property
    def running(self) -> bool:
        return bool(self._running and self._source is not None)

    # ----------------------------------------------------------------- loop
    def _loop(self) -> None:
        misses = 0
        while self._running:
            src = self._source
            if src is None:
                break
            ok, frame = src.read() if hasattr(src, "read") else (False, None)
            if ok and frame is not None:
                misses = 0
                with self._lock:
                    self._frame = frame
            else:
                misses += 1
                if misses > 60 and not isinstance(src, _Synthetic):
                    cb = self._on_lost
                    self._running = False
                    with self._lock:
                        if self._source is not None:
                            self._source.release()
                            self._source = None
                        self._frame = None
                    if cb:
                        cb("device unplugged or lost")
                    break
                time.sleep(0.05)

    # ---------------------------------------------------------------- output
    def frame_jpeg(self, max_width: int = 1600) -> Optional[bytes]:
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
        if frame is None:
            return None
        h, w = frame.shape[:2]
        if w > max_width:
            frame = cv2.resize(frame, (max_width, int(h * max_width / w)))
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return buf.tobytes() if ok else None
