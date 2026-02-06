from typing import List, Optional

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

logger = get_logger("streaming")


class ProcessFrame(object):
    """
    Процессор кадров с детекцией и трекингом.

    Автоматически отслеживает переключение режима детектора (optical/thermal)
    и использует актуальный детектор без необходимости перезапуска стрима.

    detector_manager: при передаче из Dishka используется он; иначе — get_detector_manager().
    """

    def __init__(
        self,
        camera_id: int,
        auto_ptz_manager: AutoPTZManager,
        enable_auto_tracking: bool,
        enable_detection: bool,
        detector_manager: Optional[DetectorManager] = None,
    ):
        self.camera_id = camera_id
        self.enable_auto_tracking = enable_auto_tracking
        self.enable_detection = enable_detection
        self.auto_ptz_manager = auto_ptz_manager
        self._detector_manager = detector_manager

        # Кешируем детектор и отслеживаем его режим
        self._cached_detector: Optional[ObjectDetector] = None
        self._cached_mode = None

        # Инициализация при старте
        self._init_detector()

        self.tracker: Optional[CentroidTracker] = (
            CentroidTracker() if self._cached_detector else None
        )
        self.auto_ptz: Optional[AutoPTZTracker] = (
            auto_ptz_manager.get_or_create(self.camera_id)
            if (self._cached_detector is not None and self.enable_auto_tracking)
            else None
        )

    def _get_manager(self) -> DetectorManager:
        """Детектор-менеджер: переданный из Dishka или глобальный синглтон."""
        return self._detector_manager or get_detector_manager()

    def _init_detector(self) -> None:
        """Инициализирует детектор и запоминает текущий режим."""
        if not self.enable_detection:
            self._cached_detector = None
            self._cached_mode = None
            return

        try:
            manager = self._get_manager()
            self._cached_detector = manager.get_detector()
            self._cached_mode = manager.get_current_mode()
        except Exception as exc:
            logger.error(f"Object detector unavailable: {exc}")
            self._cached_detector = None
            self._cached_mode = None

    def _get_current_detector(self) -> Optional[ObjectDetector]:
        """
        Возвращает актуальный детектор.
        Если режим изменился — обновляет кеш.
        """
        if not self.enable_detection:
            return None

        try:
            manager = self._get_manager()
            current_mode = manager.get_current_mode()

            # Если режим изменился — обновляем детектор
            if current_mode != self._cached_mode:
                logger.info(
                    f"[camera {self.camera_id}] Detector mode changed: "
                    f"{self._cached_mode} -> {current_mode}, updating..."
                )
                self._cached_detector = manager.get_detector()
                self._cached_mode = current_mode

            return self._cached_detector
        except Exception as exc:
            logger.error(f"Failed to get detector: {exc}")
            return self._cached_detector  # Возвращаем старый если есть

    def process_frame(self, frame):
        tracked_objects: List[Detection] = []

        detector = self._get_current_detector()
        if detector is not None:
            detections = detector.detect(frame)

            if self.tracker is not None:
                tracked_objects = self.tracker.update(detections)
            else:
                tracked_objects = detections

            # авто-слежение (если включено)
            if self.auto_ptz is not None and tracked_objects:
                self.auto_ptz.update(frame.shape, tracked_objects)

        return tracked_objects
