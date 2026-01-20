# app/core/streaming/mjpeg.py

from __future__ import annotations

from typing import Generator, Optional, Protocol, Callable
import socket
import dataclasses

from app.core.streaming.frame import ProcessFrame
import cv2
import json
import time
from threading import Event

from app.core.streaming.sockets_con import ConnectionConfig, ConnectionManager, SocketConnection
from logger.setup_logger import get_logger

from app.core.detection.yolo_detector import get_detector, ObjectDetector


logger = get_logger("streaming")


def _get_detector_safe(enable_detection: bool) -> Optional[ObjectDetector]:
    if not enable_detection:
        return None
    try:
        return get_detector()
    except Exception as exc:
        logger.error(f"Object detector unavailable: {exc}")
        return None


def _default_connection_factory() -> SocketConnection:
    manager = ConnectionManager(ConnectionConfig.default())
    return manager.create_connection()


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

    prcocess_manager = ProcessFrame(camera_id, enable_auto_tracking, enable_detection)


    factory = _default_connection_factory

    s: Optional[SocketConnection] = None
    try:
        s = factory()
        logger.info(f"[{camera_id}] detection sender started")

        while stop_event is None or not stop_event.is_set():
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            
            tracked_objects = prcocess_manager.process_frame(frame)

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
                s = factory()

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
    connection_config: Optional[ConnectionConfig] = None,
) -> Generator[bytes, None, None]:

    prcocess_manager = ProcessFrame(camera_id, enable_auto_tracking, enable_detection)

    with _default_connection_factory() as s:

        while True:
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            tracked_objects = prcocess_manager.process_frame(frame)

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
