from __future__ import annotations

from threading import Lock
from typing import Dict, Optional, TYPE_CHECKING

from app.core.ptz.manager import PTZCameraManager
from app.core.tracking.auto_ptz_tracker import AutoPTZTracker

if TYPE_CHECKING:
    from app.config.settings import CameraConfig


class AutoPTZManager:
    """
    Хранит AutoPTZTracker по camera_id.
    Конфиг нужен только при создании трекера (select / первый track). Далее — из кэша PTZManager.
    """

    def __init__(self, ptz_manager: PTZCameraManager) -> None:
        self._ptz_manager = ptz_manager
        self._trackers: Dict[int, AutoPTZTracker] = {}
        self._lock = Lock()

    def has_tracker(self, camera_id: int) -> bool:
        """Трекер уже создан для камеры (конфиг закэширован)."""
        with self._lock:
            return camera_id in self._trackers

    def get_or_create(
        self,
        camera_id: int,
        client_id: str | None,
        cam_cfg: "CameraConfig",
    ) -> AutoPTZTracker:
        """
        Создать или получить трекер.
        cam_cfg обязателен при первом вызове для камеры (выбирает конфиг из БД).
        """
        with self._lock:
            tracker = self._trackers.get(camera_id)
            if tracker is not None:
                return tracker
            tracker = AutoPTZTracker(
                camera_id=camera_id,
                client_id=client_id,
                ptz_manager=self._ptz_manager,
                cam_cfg=cam_cfg,
            )
            self._trackers[camera_id] = tracker
            return tracker

    def set_target(
        self,
        camera_id: int,
        track_id: Optional[int],
        cam_cfg: "CameraConfig",
    ) -> None:
        tracker = self.get_or_create(
            camera_id=camera_id, client_id=None, cam_cfg=cam_cfg
        )
        tracker.set_target(track_id)

    def clear_target(
        self,
        camera_id: int,
        cam_cfg: "CameraConfig",
    ) -> None:
        tracker = self.get_or_create(
            camera_id=camera_id, client_id=None, cam_cfg=cam_cfg
        )
        tracker.clear_target()

    def get_target(
        self,
        camera_id: int,
        cam_cfg: "CameraConfig",
    ) -> Optional[int]:
        tracker = self.get_or_create(
            camera_id=camera_id, client_id=None, cam_cfg=cam_cfg
        )
        return tracker.get_target()
