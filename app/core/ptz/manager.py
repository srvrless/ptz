from __future__ import annotations

from threading import Lock
from typing import Dict, TYPE_CHECKING

from app.core.ptz.base import BasePTZController
from app.core.ptz.factory import PTZControllerFactory

import app.core.ptz.controller  # noqa: F401 — регистрация ONVIF
import app.core.ptz.tms20_controller  # noqa: F401 — регистрация TMS-20
from logger.setup_logger import get_logger
from fastapi import HTTPException

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
        self._owners: Dict[int, str] = {}
        self._lock = Lock()

    # ---------- ownership (локальный кэш) ----------

    def set_owner(self, camera_id: int, client_id: str) -> None:
        """Запомнить владельца камеры (после успешного claim в gateway)."""
        with self._lock:
            self._owners[camera_id] = client_id

    def clear_owner(self, camera_id: int, client_id: str) -> None:
        """Снять владельца камеры (перед release в gateway)."""
        with self._lock:
            current = self._owners.get(camera_id)
            if current is None:
                return
            if current != client_id:
                raise HTTPException(status_code=423, detail="Камера занята")
            del self._owners[camera_id]

    def assert_owner(self, camera_id: int, client_id: str) -> None:
        """
        Проверить, что камера принадлежит client_id.

        - Если камера не выбрана/не захвачена в этом инстансе → 409
        - Если выбрана другим клиентом → 423
        """
        with self._lock:
            current = self._owners.get(camera_id)
        print(f"current: {current}, client_id: {client_id}")
        if current is None:
            raise HTTPException(
                status_code=409,
                detail="Камера не выбрана. Сначала вызовите select_camera.",
            )
        if current != client_id:
            raise HTTPException(status_code=423, detail="Камера занята")

    # TODO: в будущем будет один инстанс управления
    # def owned_camera_ids(self, client_id: str) -> list[int]:
    #     """Список camera_id, которыми владеет client_id (для выборок/подбора)."""
    #     with self._lock:
    #         return [cid for cid, owner in self._owners.items() if owner == client_id]

    def init_camera(self, camera_id: int, cam_cfg: "CameraConfig") -> BasePTZController:
        """
        Регистрирует конфиг камеры и создаёт контроллер.
        Вызывается при первом обращении (select, первый PTZ, track).
        """
        # ВАЖНО: не кэшируем конфиг, если контроллер не был успешно создан.
        controller = PTZControllerFactory.create(cam_cfg.ptz_type, cam_cfg)
        if controller is None:
            raise ValueError(
                f"Не удалось создать PTZ-контроллер для камеры {camera_id}"
            )

        with self._lock:
            self._config_cache[camera_id] = cam_cfg
            self._controllers[camera_id] = controller
        logger.info(f"Создан {cam_cfg.ptz_type} контроллер для камеры {camera_id}")
        return controller

    def get_controller(self, camera_id: int) -> BasePTZController:
        """
        Возвращает контроллер. Камера должна быть инициализирована через init_camera.
        """
        with self._lock:
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
        with self._lock:
            cam_cfg = self._config_cache.get(camera_id)
        if cam_cfg is None:
            raise ValueError(
                f"Конфиг камеры {camera_id} не в кэше. Сначала вызовите init_camera."
            )
        return cam_cfg

    def is_initialized(self, camera_id: int) -> bool:
        """
        Камера уже инициализирована (есть живой контроллер).

        Раньше проверялся только кэш конфига, из‑за чего при падении
        конструктора контроллера (например, TimeoutError в TMS‑20)
        камера помечалась как инициализированная без реального контроллера.
        """
        with self._lock:
            return camera_id in self._controllers

    def restart_controller(self, camera_id: int) -> BasePTZController:
        """Пересоздать контроллер. Конфиг берётся из кэша."""
        cam_cfg = self.get_cached_config(camera_id)
        controller = PTZControllerFactory.create(cam_cfg.ptz_type, cam_cfg)
        if controller is None:
            raise ValueError(
                f"Не удалось пересоздать PTZ-контроллер для камеры {camera_id}"
            )
        with self._lock:
            self._controllers[camera_id] = controller
        logger.info(f"Переинициализирован PTZ-контроллер для камеры {camera_id}")
        return controller
