# app/core/streaming/mjpeg.py

from __future__ import annotations

from typing import Generator, Optional, List

import cv2
import json
import socket
import time
from threading import Event

from app.config.settings import config
from logger.setup_logger import get_logger

from app.core.detection.yolo_detector import get_detector, ObjectDetector, Detection
from app.core.tracking.centroid_tracker import CentroidTracker
from app.core.tracking.auto_ptz_tracker import AutoPTZTracker
from app.core.tracking.auto_ptz_manager import auto_ptz_manager


logger = get_logger("streaming")


def _get_detector_safe(enable_detection: bool) -> Optional[ObjectDetector]:
    if not enable_detection:
        return None
    try:
        return get_detector()
    except Exception as exc:
        logger.error(f"Object detector unavailable: {exc}")
        return None


def _connect_sender_socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((config.HOST_RECV_SERVER, config.PORT_RECV_SERVER))
    return s


def run_detection_sender(
    camera,
    camera_id: str,
    enable_detection: bool = True,
    enable_auto_tracking: bool = True,
    stop_event: Optional[Event] = None,
) -> None:
    """
    Читает кадры из camera.get_frame(), детектит/трекает и шлёт JSON по сокету.
    НИЧЕГО не стримит как видео (нет yield).
    """

    detector = _get_detector_safe(enable_detection)
    tracker: Optional[CentroidTracker] = CentroidTracker() if detector else None

    auto_ptz: Optional[AutoPTZTracker] = (
        auto_ptz_manager.get_or_create(camera_id)
        if (detector is not None and enable_auto_tracking)
        else None
    )

    s: Optional[socket.socket] = None
    try:
        s = _connect_sender_socket()
        logger.info(f"[{camera_id}] detection sender started")

        while stop_event is None or not stop_event.is_set():
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            tracked_objects: List[Detection] = []

            if detector is not None:
                detections = detector.detect(frame)

                if tracker is not None:
                    tracked_objects = tracker.update(detections)
                else:
                    tracked_objects = detections

                # авто-слежение (если включено)
                if auto_ptz is not None and tracked_objects:
                    auto_ptz.update(frame.shape, tracked_objects)

            # После правки Detection.to_dict() тут уже будет bbox
            objects_data = [d.to_dict() for d in tracked_objects]
            payload = (json.dumps(objects_data) + "\n").encode("utf-8")

            try:
                s.sendall(payload)
            except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                logger.warning(f"[{camera_id}] socket error: {exc}; reconnecting...")
                try:
                    s.close()
                except Exception:
                    pass
                time.sleep(0.2)
                s = _connect_sender_socket()

        logger.info(f"[{camera_id}] detection sender stopped")

    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


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
        if (detector is not None and enable_auto_tracking)
        else None
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((config.HOST_RECV_SERVER, config.PORT_RECV_SERVER))

        while True:
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            tracked_objects: List[Detection] = []

            if detector is not None:
                detections = detector.detect(frame)
                tracked_objects = tracker.update(detections) if tracker else detections

                frame = detector.draw(frame, tracked_objects)

                if auto_ptz is not None and tracked_objects:
                    auto_ptz.update(frame.shape, tracked_objects)

            ok, buffer = cv2.imencode(".jpg", frame)
            if not ok:
                logger.warning("Failed to encode frame as JPEG")
                continue

            # JSON в сокет
            objects_data = [d.to_dict() for d in tracked_objects]
            s.sendall((json.dumps(objects_data) + "\n").encode("utf-8"))

            jpg = buffer.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            )
