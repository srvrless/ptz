from typing import TYPE_CHECKING, List, Optional

from app.config.settings import DetectorMode
from app.core.detection.yolo_detector import (
    Detection,
    DetectorManager,
    ObjectDetector,
    get_detector_manager,
)
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.core.tracking.auto_ptz_tracker import AutoPTZTracker
from app.core.tracking.centroid_tracker import CentroidTracker
from logger.setup_logger import get_logger

if TYPE_CHECKING:
    from app.config.settings import CameraConfig
    from app.core.camera.manager import Camera

logger = get_logger("streaming")


class ProcessFrame(object):
    """
    Процессор кадров с детекцией и трекингом.

    При смене режима детектора (optical ↔ thermal) автоматически переключает
    видеопоток камеры на соответствующий RTSP URL и сбрасывает трекер.
    """

    def __init__(
        self,
        camera_id: int,
        auto_ptz_manager: AutoPTZManager,
        enable_auto_tracking: bool,
        enable_detection: bool,
        cam_cfg: "CameraConfig",
        *,
        camera: Optional["Camera"] = None,
        detector_manager: Optional[DetectorManager] = None,
    ):
        self.camera_id = camera_id
        self.enable_auto_tracking = enable_auto_tracking
        self.enable_detection = enable_detection
        self.auto_ptz_manager = auto_ptz_manager
        self._camera = camera
        self._detector_manager = detector_manager
        self._cam_cfg = cam_cfg

        self._cached_detector: Optional[ObjectDetector] = None
        self._cached_mode = None

        self._init_detector()

        self.tracker: Optional[CentroidTracker] = (
            CentroidTracker() if self._cached_detector else None
        )
        self.auto_ptz: Optional[AutoPTZTracker] = (
            auto_ptz_manager.get_or_create(self.camera_id, self._cam_cfg)
            if (self._cached_detector is not None and self.enable_auto_tracking)
            else None
        )

    def _get_manager(self) -> DetectorManager:
        """Детектор-менеджер: переданный из Dishka или глобальный синглтон."""
        return self._detector_manager or get_detector_manager()

    def _url_for_mode(self, mode: Optional[DetectorMode]) -> str:
        """Возвращает RTSP URL, соответствующий режиму детектора."""
        if mode == DetectorMode.THERMAL:
            return self._cam_cfg.rtsp_url_ik
        return self._cam_cfg.rtsp_url

    def _init_detector(self) -> None:
        """Инициализирует детектор и гарантирует, что камера на нужном потоке."""
        if not self.enable_detection:
            self._cached_detector = None
            self._cached_mode = None
            return

        try:
            manager = self._get_manager()
            self._cached_detector = manager.get_detector()
            self._cached_mode = manager.get_current_mode()

            if self._camera is not None:
                correct_url = self._url_for_mode(self._cached_mode)
                self._camera.switch_url(correct_url)
        except Exception as exc:
            logger.error(f"Object detector unavailable: {exc}")
            self._cached_detector = None
            self._cached_mode = None

    def _get_current_detector(self) -> Optional[ObjectDetector]:
        """
        Возвращает актуальный детектор.
        При смене режима — переключает видеопоток камеры и сбрасывает трекер.
        """
        if not self.enable_detection:
            return None

        try:
            manager = self._get_manager()
            current_mode = manager.get_current_mode()

            if current_mode != self._cached_mode:
                logger.info(
                    f"[camera {self.camera_id}] Detector mode changed: "
                    f"{self._cached_mode} -> {current_mode}, updating..."
                )
                self._cached_detector = manager.get_detector()

                if self._camera is not None:
                    new_url = self._url_for_mode(current_mode)
                    logger.info(
                        f"[camera {self.camera_id}] Switching stream to: {new_url}"
                    )
                    self._camera.switch_url(new_url)

                if self.tracker is not None:
                    self.tracker.reset()
                    logger.info(
                        f"[camera {self.camera_id}] Tracker reset after mode change"
                    )

                self._cached_mode = current_mode

            return self._cached_detector
        except Exception as exc:
            logger.error(f"Failed to get detector: {exc}")
            return self._cached_detector

    def process_frame(self, frame):
        tracked_objects: List[Detection] = []

        detector = self._get_current_detector()
        if detector is not None:
            detections = detector.detect(frame)

            if self.tracker is not None:
                tracked_objects = self.tracker.update(detections)
            else:
                tracked_objects = detections

            if self.auto_ptz is not None and tracked_objects:
                self.auto_ptz.update(frame.shape, tracked_objects)

        return tracked_objects
