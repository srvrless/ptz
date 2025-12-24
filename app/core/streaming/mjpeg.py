from typing import Generator, Optional, Tuple, Any, Dict, List

import cv2
import json
import socket
from app.config.settings import config

from logger.setup_logger import get_logger
from app.core.detection.yolo_detector import get_detector, ObjectDetector, Detection
from app.core.tracking.centroid_tracker import CentroidTracker
from app.core.tracking.auto_ptz_tracker import AutoPTZTracker
from app.core.tracking.auto_ptz_manager import auto_ptz_manager
from threading import Lock

logger = get_logger("mjpeg_stream")


def _get_detector_safe(enable_detection: bool) -> Optional[ObjectDetector]:
    """
    Пытается инициализировать детектор.
    Если не получилось — логируем и возвращаем None,
    стрим продолжается без разметки.
    """
    if not enable_detection:
        return None

    try:
        return get_detector()
    except Exception as exc:
        logger.error(f"Object detector unavailable, streaming raw frames: {exc}")
        return None


def generate_mjpeg(
    camera,
    camera_id: str,
    enable_detection: bool = True,
    enable_auto_tracking: bool = True,
) -> Generator[bytes, None, None]:

    detector = _get_detector_safe(enable_detection)
    tracker: Optional[CentroidTracker] = CentroidTracker() if detector else None
    auto_ptz: Optional[AutoPTZTracker] = (
        auto_ptz_manager.get_or_create(camera_id)
        if (enable_detection and enable_auto_tracking)
        else None
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((config.HOST_RECV_SERVER, config.PORT_RECV_SERVER))
        while True:
            frame = camera.get_frame()
            if frame is None:
                    # можно добавить sleep(0.01), если нужно разгрузить CPU

                continue

            tracked_objects: list[Detection] = []

            if detector is not None:

                detections = detector.detect(frame)

                if tracker is not None:
                    tracked_objects = tracker.update(detections)
                else:
                    tracked_objects = detections

                    # рисуем уже с ID
                frame = detector.draw(frame, tracked_objects)

                    # авто-слежение PTZ за выбранным объектом
                if auto_ptz is not None and tracked_objects:
                    auto_ptz.update(frame.shape, tracked_objects)

            ok, buffer = cv2.imencode(".jpg", frame)
            if not ok:
                logger.warning("Не удалось закодировать кадр в JPEG")
                continue

            jpg = buffer.tobytes()

            objects_data = list(map(Detection.to_dict, tracked_objects))
            
            json_data = json.dumps(objects_data).encode() + b"\n"
            s.sendall(json_data)

            yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                )
