from __future__ import annotations

from typing import Dict, TYPE_CHECKING

from app.core.ptz.base import BasePTZController
from app.core.ptz.factory import PTZControllerFactory

import app.core.ptz.controller  # noqa: F401 — регистрация ONVIF
import app.core.ptz.tms20_controller  # noqa: F401 — регистрация TMS-20
from logger.setup_logger import get_logger

if TYPE_CHECKING:
    from app.config.settings import CameraConfig

logger = get_logger("ptz_camera_manager")


class PTZCameraManager:
    """
    PTZ-контроллеры создаются lazy. Конфиг кэшируется при инициализации (select / первый PTZ).
    """

    def __init__(self) -> None:
        self._controllers: Dict[int, BasePTZController] = {}
        self._config_cache: Dict[int, "CameraConfig"] = {}

    def init_camera(self, camera_id: int, cam_cfg: "CameraConfig") -> BasePTZController:
        """
        Регистрирует конфиг камеры и создаёт контроллер.
        Вызывается при первом обращении (select, первый PTZ, track).
        """
        self._config_cache[camera_id] = cam_cfg
        controller = PTZControllerFactory.create(cam_cfg.ptz_type, cam_cfg)
        if controller is None:
            raise ValueError(f"Не удалось создать PTZ-контроллер для камеры {camera_id}")
        self._controllers[camera_id] = controller
        logger.info(f"Создан {cam_cfg.ptz_type} контроллер для камеры {camera_id}")
        return controller

    def get_controller(self, camera_id: int) -> BasePTZController:
        """
        Возвращает контроллер. Камера должна быть инициализирована через init_camera.
        """
        controller = self._controllers.get(camera_id)
        if controller is None:
            raise ValueError(
                f"Камера {camera_id} не инициализирована. Сначала вызовите select или PTZ-команду."
            )
        return controller

    def get_or_init_controller(
        self, camera_id: int, cam_cfg: "CameraConfig"
    ) -> BasePTZController:
        """Если камера не инициализирована — регистрирует конфиг и создаёт контроллер."""
        if not self.is_initialized(camera_id):
            return self.init_camera(camera_id, cam_cfg)
        return self.get_controller(camera_id)

    def get_cached_config(self, camera_id: int) -> "CameraConfig":
        """Конфиг из кэша. Вызывать только если камера уже инициализирована."""
        cam_cfg = self._config_cache.get(camera_id)
        if cam_cfg is None:
            raise ValueError(
                f"Конфиг камеры {camera_id} не в кэше. Сначала вызовите init_camera."
            )
        return cam_cfg

    def is_initialized(self, camera_id: int) -> bool:
        """Камера уже инициализирована (конфиг и контроллер в кэше)."""
        return camera_id in self._config_cache

    def restart_controller(self, camera_id: int) -> BasePTZController:
        """Пересоздать контроллер. Конфиг берётся из кэша."""
        cam_cfg = self.get_cached_config(camera_id)
        controller = PTZControllerFactory.create(cam_cfg.ptz_type, cam_cfg)
        if controller is None:
            raise ValueError(f"Не удалось пересоздать PTZ-контроллер для камеры {camera_id}")
        self._controllers[camera_id] = controller
        logger.info(f"Переинициализирован PTZ-контроллер для камеры {camera_id}")
        return controller
