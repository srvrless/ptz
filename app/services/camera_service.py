from __future__ import annotations

from threading import Event, Lock, Thread
from typing import Generator, List, Optional

from app.config.settings import AppConfig
from app.core.camera.manager import CameraConnection, CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.streaming.mjpeg import generate_mjpeg, run_detection_sender
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

    # старое оставляем (если нужно для отладки MJPEG)
    def get_mjpeg_stream(
        self,
        uow: InterfaceUnitOfWork,
        camera_id: int,
        enable_detection: bool = True,
    ) -> Generator[bytes, None, None]:
        cam_cfg = self.get_camera_config(uow, camera_id)

        conn = CameraConnection(url=cam_cfg.rtsp_url)
        camera = self.camera_manager.get_or_create(camera_id, conn)

        logger.info(
            f"Запуск MJPEG-стрима для {camera_id}, "
            f"детекция: {'on' if enable_detection else 'off'}"
        )
        return generate_mjpeg(
            camera,
            camera_id=camera_id,
            auto_ptz_manager=self.auto_ptz_manager,
            cam_cfg=cam_cfg,
            detector_manager=self.detector_manager,
            enable_detection=enable_detection,
            enable_auto_tracking=True,
        )

    # НОВОЕ: выбрать камеру и запустить фоновую обработку (без MJPEG)
    def select_camera(
        self,
        uow: InterfaceUnitOfWork,
        camera_id: int,
        enable_detection: bool = True,
        enable_auto_tracking: bool = True,
    ) -> None:
        cam_cfg = self.get_camera_config(uow, camera_id)

        conn = CameraConnection(url=cam_cfg.rtsp_url)
        camera = self.camera_manager.get_or_create(camera_id, conn)

        with self._lock:
            # если уже выбрана и поток жив — ничего не делаем
            if (
                self._selected_camera_id == camera_id
                and self._worker_thread is not None
                and self._worker_thread.is_alive()
            ):
                return

            # стопаем старый воркер
            self._stop_worker_locked()

            stop_event = Event()
            worker = Thread(
                target=run_detection_sender,
                kwargs=dict(
                    camera=camera,
                    camera_id=camera_id,
                    auto_ptz_manager=self.auto_ptz_manager,
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
            self._stop_worker_locked()
            self._selected_camera_id = None

    def _stop_worker_locked(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)

        self._stop_event = None
        self._worker_thread = None
