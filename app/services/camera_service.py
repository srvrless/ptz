from __future__ import annotations

from threading import Event, Lock, Thread
from typing import List, Optional

from app.config.settings import AppConfig, DetectorMode
from app.core.camera.manager import CameraConnection, CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.streaming.mjpeg import run_detection_sender
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.schemas.camera import (
    CameraResponse,
    CreateCamera,
    CreateCameraResponse,
    UpdateCamera,
    UpdateCameraResponse,
)
from app.utils.uow import InterfaceUnitOfWork
from app.exceptions import CameraNotFoundError
from app.services.camera_gateway_client import CameraGatewayClient
from logger.setup_logger import get_logger

logger = get_logger("camera_service")


class CameraService:
    def __init__(
        self,
        camera_manager: CameraManager,
        auto_ptz_manager: AutoPTZManager,
        detector_manager: DetectorManager,
        config: AppConfig,
        camera_gateway: CameraGatewayClient,
    ) -> None:
        self.camera_manager = camera_manager
        self.auto_ptz_manager = auto_ptz_manager
        self.detector_manager = detector_manager
        self.config = config
        self._lock = Lock()
        self._selected_camera_id: Optional[str] = None
        self._worker_thread: Optional[Thread] = None
        self._stop_event: Optional[Event] = None
        self._camera_gateway = camera_gateway

    def get_camera_config(
        self,
        uow: InterfaceUnitOfWork,
        camera_id: int,
    ):
        """Получить конфиг камеры из БД. Конвертация внутри with — объект не detached."""
        from app.config.settings import CameraConfig

        camera_cfg = self._camera_gateway.get_camera_config_by_id(camera_id)
        if camera_cfg is None:
            logger.warning(f"Camera not found: {camera_id}")
            raise CameraNotFoundError(str(camera_id))
        return camera_cfg

    def _rtsp_url_for_current_mode(self, cam_cfg) -> str:
        """Возвращает RTSP URL, соответствующий текущему режиму детектора."""
        current_mode = self.detector_manager.get_current_mode()
        if current_mode == DetectorMode.THERMAL:
            return cam_cfg.rtsp_url_ik
        return cam_cfg.rtsp_url

    def _get_camera_for_current_mode(self, camera_id: int, cam_cfg):
        """Создаёт/получает камеру и гарантирует, что она на правильном потоке."""
        url = self._rtsp_url_for_current_mode(cam_cfg)
        conn = CameraConnection(url=url)
        camera = self.camera_manager.get_or_create(camera_id, conn)
        camera.switch_url(url)
        return camera

    def select_camera(
        self,
        uow: InterfaceUnitOfWork,
        camera_id: int,
        enable_detection: bool = True,
        enable_auto_tracking: bool = True,
    ) -> None:
        cam_cfg = self.get_camera_config(uow, camera_id)

        auto_ptz = self.auto_ptz_manager.get_or_create(camera_id, cam_cfg)

        with self._lock:
            if (
                self._selected_camera_id == camera_id
                and self._worker_thread is not None
                and self._worker_thread.is_alive()
            ):
                return

            old_camera_id = self._selected_camera_id

            # 1. Останавливаем старый detection-воркер
            self._stop_worker_locked()

            # 2. Останавливаем старую камеру (reader thread + VideoCapture)
            #    чтобы get_frame() возвращал None и воркер точно не слал данные
            if old_camera_id is not None and old_camera_id != camera_id:
                self.camera_manager.release(old_camera_id)

            # 3. Создаём/получаем камеру для нового ID
            camera = self._get_camera_for_current_mode(camera_id, cam_cfg)

            stop_event = Event()
            worker = Thread(
                target=run_detection_sender,
                kwargs=dict(
                    camera=camera,
                    camera_id=camera_id,
                    auto_ptz=auto_ptz,
                    cam_cfg=cam_cfg,
                    detector_manager=self.detector_manager,
                    enable_detection=enable_detection,
                    enable_auto_tracking=enable_auto_tracking,
                    stop_event=stop_event,
                ),
                daemon=True,
            )
            worker.start()

            self._selected_camera_id = camera_id
            self._stop_event = stop_event
            self._worker_thread = worker

            logger.info(f"Selected camera: {camera_id}")

    def get_selected_camera_id(self) -> Optional[str]:
        with self._lock:
            return self._selected_camera_id

    def stop_selected_camera(self) -> None:
        with self._lock:
            old_camera_id = self._selected_camera_id
            self._stop_worker_locked()
            if old_camera_id is not None:
                self.camera_manager.release(old_camera_id)
            self._selected_camera_id = None

    def _stop_worker_locked(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
            if self._worker_thread.is_alive():
                logger.error(
                    f"Detection worker for camera {self._selected_camera_id} "
                    f"did not stop within 5s — possible data leak to socket"
                )

        self._stop_event = None
        self._worker_thread = None
