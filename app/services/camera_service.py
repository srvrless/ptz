from __future__ import annotations

from typing import Any, Dict, Generator

from logger.setup_logger import get_logger

from app.config.settings import config
from app.core.camera.manager import camera_manager, CameraConnection
from app.core.streaming.mjpeg import generate_mjpeg
from app.utils.serializers import serialize_cameras

logger = get_logger("camera_service")


class CameraNotFoundError(Exception):
    """Камера с указанным ID не найдена в конфиге."""

class CameraService:

    def list_cameras(self) -> Dict[str, Any]:
        return serialize_cameras(config.cameras)

    def get_camera_config(self, camera_id: str):
        cam_cfg = config.cameras.get(camera_id)
        if not cam_cfg:
            logger.warning(f"Camera not found: {camera_id}")
            raise CameraNotFoundError(f"Camera not found: {camera_id}")
        return cam_cfg


    def get_mjpeg_stream(
        self,
        camera_id: str,
        enable_detection: bool = True,
    ) -> Generator[bytes, None, None]:
        cam_cfg = self.get_camera_config(camera_id)

        # Низкоуровневое подключение к камере
        conn = CameraConnection(url=cam_cfg.rtsp_url)
        camera = camera_manager.get_or_create(camera_id, conn)

        logger.info(
            f"Запуск MJPEG-стрима для {camera_id}, "
            f"детекция: {'on' if enable_detection else 'off'}"
        )
        return generate_mjpeg(
            camera,
            camera_id=camera_id,
            enable_detection=enable_detection,
            enable_auto_tracking=True,  # при необходимости можно сделать параметром
        )

camera_service = CameraService()
