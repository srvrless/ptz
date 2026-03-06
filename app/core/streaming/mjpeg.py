from __future__ import annotations

import json
import time
from threading import Event
from typing import Optional


from app.core.detection.yolo_detector import (
    DetectorManager,
    ObjectDetector,
    get_detector,
)
from app.core.streaming.frame import ProcessFrame
from app.core.streaming.sockets_con import (
    ConnectionConfig,
    ConnectionManager,
    SocketConnection,
)
from app.core.tracking.auto_ptz_tracker import AutoPTZTracker
from logger.setup_logger import get_logger

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
    camera_id: int,
    auto_ptz: AutoPTZTracker,
    cam_cfg,
    *,
    enable_detection: bool = True,
    enable_auto_tracking: bool = True,
    stop_event: Optional[Event] = None,
    detector_manager: Optional[DetectorManager] = None,
) -> None:
    """
    Читает кадры из camera.get_frame(), детектит/трекает и шлёт JSON по сокету.

    Args:
        camera: Camera instance
        camera_id: ID камеры
        auto_ptz_manager: AutoPTZManager для управления слежением
        cam_cfg: Конфиг камеры из БД (для PTZ-трекера)
    """
    prcocess_manager = ProcessFrame(
        camera_id=camera_id,
        auto_ptz=auto_ptz,
        enable_auto_tracking=enable_auto_tracking,
        enable_detection=enable_detection,
        cam_cfg=cam_cfg,
        camera=camera,
        detector_manager=detector_manager,
    )

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
