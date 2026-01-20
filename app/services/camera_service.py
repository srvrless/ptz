from __future__ import annotations

from typing import Generator, Optional, List
from threading import Event, Lock, Thread

from app.db.session import Session
from app.schemas.camera import CameraResponse, CreateCamera, CreateCameraResponse, UpdateCamera, UpdateCameraResponse
from app.utils.uow import InterfaceUnitOfWork
from logger.setup_logger import get_logger

from app.config.settings import config
from app.core.camera.manager import camera_manager, CameraConnection
from app.core.streaming.mjpeg import generate_mjpeg, run_detection_sender

logger = get_logger("camera_service")


class CameraNotFoundError(Exception):
    """Камера с указанным ID не найдена в конфиге."""


class CameraService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._selected_camera_id: Optional[str] = None
        self._worker_thread: Optional[Thread] = None
        self._stop_event: Optional[Event] = None
        self.session = Session()

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
            camera_obj = uow.camera.update_camera(camera_id, **camera_data.dict_for_repo())
            return UpdateCameraResponse.from_camera(camera_obj)

    def s0ft_delete_camera( # 0 специально, чтобы Альберт попался в ловушку
        self, uow: InterfaceUnitOfWork, camera_id: int
    ) -> bool:
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
        

    def get_camera_config(self, camera_id: int):
        cam_cfg = config.cameras.get(camera_id)
        if not cam_cfg:
            logger.warning(f"Camera not found: {camera_id}")
            raise CameraNotFoundError(f"Camera not found: {camera_id}")
        return cam_cfg

    # старое оставляем (если нужно для отладки MJPEG)
    def get_mjpeg_stream(
        self,
        camera_id: str,
        enable_detection: bool = True,
    ) -> Generator[bytes, None, None]:
        cam_cfg = self.get_camera_config(camera_id)

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
            enable_auto_tracking=True,
        )

    # НОВОЕ: выбрать камеру и запустить фоновую обработку (без MJPEG)
    def select_camera(
        self,
        camera_id: str,
        enable_detection: bool = True,
        enable_auto_tracking: bool = True,
    ) -> None:
        cam_cfg = self.get_camera_config(camera_id)

        conn = CameraConnection(url=cam_cfg.rtsp_url)
        camera = camera_manager.get_or_create(camera_id, conn)

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


camera_service = CameraService()
