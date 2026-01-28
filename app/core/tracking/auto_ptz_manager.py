from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

from app.core.tracking.auto_ptz_tracker import AutoPTZTracker


class AutoPTZManager:
    """
    Хранит AutoPTZTracker по camera_id, чтобы один и тот же трекер
    использовался и стримом, и API.
    """

    def __init__(self) -> None:
        self._trackers: Dict[str, AutoPTZTracker] = {}
        self._lock = Lock()

    def get_or_create(self, camera_id: int) -> AutoPTZTracker:
        with self._lock:
            tracker = self._trackers.get(camera_id)
            if tracker is None:
                tracker = AutoPTZTracker(camera_id)
                self._trackers[camera_id] = tracker
            return tracker

    def set_target(self, camera_id: int, track_id: Optional[int]) -> None:
        tracker = self.get_or_create(camera_id)
        tracker.set_target(track_id)

    def clear_target(self, camera_id: int) -> None:
        tracker = self.get_or_create(camera_id)
        tracker.clear_target()

    def get_target(self, camera_id: int) -> Optional[int]:
        tracker = self.get_or_create(camera_id)
        return tracker.get_target()


auto_ptz_manager = AutoPTZManager()
