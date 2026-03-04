from __future__ import annotations

from threading import Event, Lock, Thread
from typing import Generator, List, Optional

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
from logger.setup_logger import get_logger

logger = get_logger("camera_service")


class CameraService:
    def __init__(
        self,
        camera_manager: CameraManager,
        auto_ptz_manager: AutoPTZManager,
        detector_manager: DetectorManager,
        config: AppConfig,
    ) -> None:
        self.camera_manager = camera_manager
        self.auto_ptz_manager = auto_ptz_manager
        self.detector_manager = detector_manager
        self.config = config
        self._lock = Lock()
        self._selected_camera_id: Optional[str] = None
        self._worker_thread: Optional[Thread] = None
        self._stop_event: Optional[Event] = None

    def list_cameras(self, uow: InterfaceUnitOfWork) -> List[CameraResponse]:
        """Получить список всех камер в виде DTO"""
        with uow:
            cameras = uow.camera.get_all_cameras()
            return [CameraResponse.from_camera(camera) for camera in cameras]

    def create_camera(
        self, uow: InterfaceUnitOfWork, camera_data: CreateCamera
    ) -> CreateCameraResponse:
        with uow:
            camera_obj = uow.camera.create_camera(**camera_data.dict_for_repo())
            return CreateCameraResponse.from_camera(camera_obj)

    def update_camera(
        self, uow: InterfaceUnitOfWork, camera_id: int, camera_data: UpdateCamera
    ) -> UpdateCameraResponse:
        with uow:
            camera_obj = uow.camera.update_camera(
                camera_id, **camera_data.dict_for_repo()
            )
            if camera_obj is None:
                raise CameraNotFoundError(camera_id)
            return UpdateCameraResponse.from_camera(camera_obj)

    def soft_delete_camera(self, uow: InterfaceUnitOfWork, camera_id: int) -> bool:
        with uow:
            camera = uow.camera.delete_camera(camera_id)
            return camera

    def get_camera_by_id(
        self, uow: InterfaceUnitOfWork, camera_id: int
    ) -> Optional[CameraResponse]:
        with uow:
            camera = uow.camera.get_camera_by_id(camera_id)
            if camera is None:
                return None
            return CameraResponse.from_camera(camera)

    def get_camera_config(
        self,
        uow: InterfaceUnitOfWork,
        camera_id: int,
    ):
        """Получить конфиг камеры из БД. Конвертация внутри with — объект не detached."""
        from app.config.settings import CameraConfig

        with uow:
            camera = uow.camera.get_camera_by_id(camera_id)
            if camera is None:
                logger.warning(f"Camera not found: {camera_id}")
                raise CameraNotFoundError(camera_id)
            return CameraConfig.from_db_model(camera)

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
