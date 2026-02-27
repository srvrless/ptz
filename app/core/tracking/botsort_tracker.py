"""
Per-camera object tracker based on ultralytics BoT-SORT.

Advantages over the previous CentroidTracker:
- Kalman Filter for robust motion prediction
- Hungarian algorithm for globally optimal detection↔track assignment
- GMC (Global Motion Compensation) via sparse optical flow —
  correctly compensates PTZ pan / tilt / zoom camera movement
- ByteTrack two-stage matching (high + low confidence detections) —
  dramatically reduces ID switches caused by detection flicker
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import List

import numpy as np

from ultralytics.trackers.basetrack import BaseTrack
from ultralytics.trackers.bot_sort import BOTSORT

from app.core.detection.yolo_detector import Detection
from logger.setup_logger import get_logger

logger = get_logger("botsort_tracker")


class _Detections:
    """
    Lightweight adapter that provides the attributes and indexing
    expected by ``BYTETracker.update()`` / ``BOTSORT.update()``:

    * ``.conf``   — confidence scores  (1-D ndarray)
    * ``.cls``    — class IDs          (1-D ndarray)
    * ``.xywh``   — boxes in center-wh (N×4 ndarray)
    * ``.xyxy``   — boxes in x1y1x2y2  (N×4 ndarray, used by GMC)
    * ``__len__`` — number of detections
    * ``__getitem__`` — boolean / integer mask indexing
    """

    __slots__ = ("conf", "cls", "xywh", "xyxy")

    def __init__(self, detections: List[Detection]) -> None:
        if not detections:
            self.conf = np.empty(0, dtype=np.float32)
            self.cls = np.empty(0, dtype=np.float32)
            self.xywh = np.empty((0, 4), dtype=np.float32)
            self.xyxy = np.empty((0, 4), dtype=np.float32)
            return

        xyxy = np.array([d.bbox for d in detections], dtype=np.float32)
        self.xyxy = xyxy
        self.conf = np.array([d.conf for d in detections], dtype=np.float32)
        self.cls = np.array([d.cls_id for d in detections], dtype=np.float32)

        # xyxy → xywh  (center_x, center_y, width, height)
        self.xywh = np.column_stack(
            [
                (xyxy[:, 0] + xyxy[:, 2]) / 2.0,
                (xyxy[:, 1] + xyxy[:, 3]) / 2.0,
                xyxy[:, 2] - xyxy[:, 0],
                xyxy[:, 3] - xyxy[:, 1],
            ]
        )

    # -- required by BYTETracker.update() for mask-based splitting --

    def __len__(self) -> int:
        return len(self.conf)

    def __getitem__(self, idx):
        """Support boolean / integer-array indexing (e.g. ``results[mask]``)."""
        new = object.__new__(_Detections)
        new.conf = self.conf[idx]
        new.cls = self.cls[idx]
        new.xywh = self.xywh[idx]
        new.xyxy = self.xyxy[idx]
        return new


class BOTSortTracker:
    """
    Per-camera object tracker using ultralytics **BoT-SORT**.

    Each camera must have its own ``BOTSortTracker`` instance
    (tracker state — Kalman filters, GMC optical flow history —
    is per-camera).

    The YOLO detection model stays **shared** across cameras;
    only this tracker is per-camera.

    Parameters can be overridden via ``**kwargs`` passed to
    ``__init__``; see ``_DEFAULT_CFG`` for the full list.
    """

    _DEFAULT_CFG: dict = dict(
        # --- ByteTrack core ---
        track_high_thresh=0.5,      # 1st-stage matching confidence gate
        track_low_thresh=0.1,       # 2nd-stage matching confidence gate
        new_track_thresh=0.6,       # min conf to create a new track
        track_buffer=60,            # ≈2 s @ 30 fps: how long to keep lost tracks
        match_thresh=0.8,           # IoU gate for matching
        fuse_score=False,           # fuse detection confidence into cost matrix
        # --- BoT-SORT specific ---
        gmc_method="sparseOptFlow",  # camera motion compensation method
        proximity_thresh=0.5,        # spatial proximity for Re-ID fusion
        appearance_thresh=0.25,      # appearance similarity for Re-ID fusion
        with_reid=False,             # Re-ID disabled (no extra model needed)
    )

    def __init__(self, *, frame_rate: int = 30, **overrides) -> None:
        cfg = {**self._DEFAULT_CFG, **overrides}
        self._args = SimpleNamespace(**cfg)
        self._frame_rate = frame_rate
        self._tracker = BOTSORT(self._args, frame_rate=frame_rate)
        logger.info(
            "BOTSortTracker initialized (fps=%d, gmc=%s, track_buffer=%d)",
            frame_rate,
            cfg["gmc_method"],
            cfg["track_buffer"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """
        Reset all tracker state (call on video-stream switch, etc.).

        Creates a fresh BOTSORT instance (including GMC optical-flow
        history) but **preserves the global track-ID counter** so new
        tracks receive unique IDs that cannot collide with stale
        references held by ``AutoPTZTracker``.
        """
        saved_count = BaseTrack._count
        self._tracker = BOTSORT(self._args, frame_rate=self._frame_rate)
        BaseTrack._count = saved_count
        logger.debug(
            "BOTSortTracker reset (id counter kept at %d)", saved_count
        )

    def update(
        self,
        detections: List[Detection],
        frame: np.ndarray,
    ) -> List[Detection]:
        """
        Feed detections for the current frame and return tracked objects.

        Args:
            detections: raw detections from ``ObjectDetector.detect()``.
            frame: BGR frame (needed for GMC sparse optical flow).

        Returns:
            List of ``Detection`` with ``.track_id`` populated.
            Only confirmed (activated) tracks are returned.
        """
        adapter = _Detections(detections)
        tracks = self._tracker.update(adapter, frame)

        if len(tracks) == 0:
            return []

        # tracks shape (N, 8):
        #   [x1, y1, x2, y2, track_id, conf, cls, det_idx]
        result: List[Detection] = []
        for row in tracks:
            idx = int(row[7])
            name = detections[idx].name if 0 <= idx < len(detections) else None

            result.append(
                Detection(
                    bbox=(int(row[0]), int(row[1]), int(row[2]), int(row[3])),
                    cls_id=int(row[6]),
                    conf=float(row[5]),
                    track_id=int(row[4]),
                    name=name,
                )
            )

        return result

