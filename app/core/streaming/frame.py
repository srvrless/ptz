from typing import List, Optional

from app.core.detection.yolo_detector import Detection, ObjectDetector, get_detector
from app.core.tracking.auto_ptz_manager import auto_ptz_manager
from app.core.tracking.auto_ptz_tracker import AutoPTZTracker
from app.core.tracking.centroid_tracker import CentroidTracker
from logger.setup_logger import get_logger

logger = get_logger("streaming")


class ProcessFrame(object):
    def __init__(
        self, camera_id: str, enable_auto_tracking: bool, enable_detection: bool
    ):
        self.camera_id = camera_id
        self.enable_auto_tracking = enable_auto_tracking
        self.enable_detection = enable_detection
        self.detector = self._get_detector_safe(self.enable_detection)
        self.tracker: Optional[CentroidTracker] = (
            CentroidTracker() if self.detector else None
        )
        self.auto_ptz: Optional[AutoPTZTracker] = (
            auto_ptz_manager.get_or_create(self.camera_id)
            if (self.detector is not None and self.enable_auto_tracking)
            else None
        )

    def _get_detector_safe(self, enable_detection: bool) -> Optional[ObjectDetector]:
        if not enable_detection:
            return None
        try:
            return get_detector()
        except Exception as exc:
            logger.error(f"Object detector unavailable: {exc}")
            return None

    def process_frame(self, frame):
        tracked_objects: List[Detection] = []
        self.detector
        if self.detector is not None:
            detections = self.detector.detect(frame)

            if self.tracker is not None:
                tracked_objects = self.tracker.update(detections)
            else:
                tracked_objects = detections

            # авто-слежение (если включено)
            if self.auto_ptz is not None and tracked_objects:
                self.auto_ptz.update(frame.shape, tracked_objects)

        return tracked_objects
