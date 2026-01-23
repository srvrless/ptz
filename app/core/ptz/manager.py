from __future__ import annotations

from typing import Dict, Optional

from app.config.settings import config
from app.core.ptz.base import BasePTZController
from app.core.ptz.controller import PTZController
from app.core.ptz.tms20_controller import Tms20PTZController
from logger.setup_logger import get_logger

logger = get_logger("ptz_camera_manager")


class PTZCameraManager:
    """
    Менеджер PTZ-камер: хранит BasePTZController по camera_id.
    Умеет создавать либо ONVIF, либо TMS-20 контроллер в зависимости от конфигурации.
    """

    def __init__(self):
        self._controllers: Dict[int, BasePTZController] = {}
        self._init_all_cameras()

    def _create_controller_for(self, camera_id: int) -> Optional[BasePTZController]:
        cam_cfg = config.cameras.get(camera_id)
        if not cam_cfg:
            logger.error(f"Камера {camera_id} отсутствует в конфиге")
            return None

        if cam_cfg.is_tms20():
            logger.info(f"Создаём TMS-20 PTZController для {camera_id}")
            return Tms20PTZController(
                host=cam_cfg.host,
                port=cam_cfg.port or 1470,
                cam_lat=cam_cfg.lat,
                cam_lon=cam_cfg.lon,
                cam_h=cam_cfg.height,
                cam_rate=cam_cfg.rate,
            )
        else:
            logger.info(f"Создаём ONVIF PTZController для {camera_id}")
            return PTZController(
                host=cam_cfg.host,
                user=cam_cfg.user,
                password=cam_cfg.password,
                port=cam_cfg.port,
                cam_rate=cam_cfg.rate,
                cam_lat=cam_cfg.lat,
                cam_lon=cam_cfg.lon,
                cam_h=cam_cfg.height,
            )

    def _init_all_cameras(self) -> None:
        for camera_id in config.cameras.keys():
            try:
                controller = self._create_controller_for(camera_id)
                if controller:
                    self._controllers[camera_id] = controller
                    logger.info(f"PTZController инициализирован: {camera_id}")
            except Exception as e:
                logger.error(f"Ошибка инициализации PTZController {camera_id}: {e}")

    def get_controller(self, camera_id: int) -> Optional[BasePTZController]:
        controller = self._controllers.get(camera_id)
        if controller is None:
            controller = self._create_controller_for(camera_id)
            if controller:
                self._controllers[camera_id] = controller
        if controller is None:
            logger.warning(f"PTZController для камеры {camera_id} не найден")
        return controller

    def restart_camera(self, camera_id: int) -> Optional[BasePTZController]:
        logger.info(f"Переинициализация PTZ-контроллера для {camera_id}")
        controller = self._create_controller_for(camera_id)
        if controller:
            self._controllers[camera_id] = controller
        return controller


ptz_camera_manager = PTZCameraManager()
