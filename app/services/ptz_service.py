from __future__ import annotations

import re
from typing import Any, Dict, Optional

from app.config.settings import config
from app.core.ptz.controller import PTZController
from app.core.ptz.manager import ptz_camera_manager
from logger.setup_logger import get_logger

logger = get_logger("ptz_service")


class PTZControllerNotFoundError(Exception):
    """PTZ-контроллер для указанной камеры не найден."""


class PTZMoveError(Exception):
    """Ошибка при наведении PTZ на цель."""


class PTZService:
    """
    Сервисный слой для управления PTZ-камерами.
    Здесь инкапсулируем:
      - поиск контроллера,
      - работу с radar_id / heights,
      - решение, когда делать restart камеры.
    """

    def _get_controller(self, camera_id: int) -> PTZController:
        controller = ptz_camera_manager.get_controller(camera_id)
        if controller is None:
            logger.warning(f"PTZController not found for camera {camera_id}")
            raise PTZControllerNotFoundError(
                f"PTZController not found for camera {camera_id}"
            )
        return controller

    def _get_radar_height(self, radar_id: int) -> float:
        try:
            return config.heights[radar_id - 1]
        except IndexError:
            raise ValueError(f"Invalid radar_id: {radar_id}")

    def _parse_camera_id(self, camera_id: str | int) -> int:
        """
        Convert camera_id to integer.
        Handles formats: "camera1" -> 1, "1" -> 1, 1 -> 1
        """
        if isinstance(camera_id, str):
            match = re.search(r'\d+', camera_id)
            if match:
                return int(match.group())
            else:
                raise ValueError(f"Invalid camera_id format: {camera_id}")
        return int(camera_id)

    # ---------- high-level операции ----------

    def move_to_target(
        self,
        camera_id: str | int,
        *,
        lat: float,
        lon: float,
        height: float,
        zoom: Optional[float] = None,
        radar_id: int = 1,
        restart_before_move: bool = True,
    ) -> Dict[str, Any]:
        """
        Навести PTZ-камеру на цель по гео-координатам.
        Возвращает dict с результатом:
        { "status": "ok", "azimut": <float> }

        Бросает:
          - PTZControllerNotFoundError
          - PTZMoveError
          - ValueError (если radar_id некорректен)
        """
        # Convert camera_id string to int (e.g., "camera1" -> 1 or "1" -> 1)
        camera_id_int = self._parse_camera_id(camera_id)
        radar_h = self._get_radar_height(radar_id)

        if restart_before_move:
            logger.info(f"Restart PTZ controller before move: {camera_id}")
            ptz_camera_manager.restart_camera(camera_id_int)

        controller = self._get_controller(camera_id_int)

        target_az = controller.search_target(
            target_lat=lat,
            target_lon=lon,
            target_h=height,
            radar_h=radar_h,
            zoom=zoom,
        )

        if target_az is None:
            logger.error(f"PTZ move_to_target failed for {camera_id}")
            raise PTZMoveError("Failed to move PTZ to target")

        logger.info(f"PTZ {camera_id} moved to azimuth {target_az:.2f}")
        return {"status": "ok", "azimut": float(target_az)}

    def continuous_move(
        self,
        camera_id: str | int,
        *,
        x: float,
        y: float,
        zoom: float = 0.0,
    ) -> None:
        """
        Непрерывное движение PTZ.
        x, y, zoom — скорости в диапазоне [-1, 1].
        """
        # Convert camera_id string to int (e.g., "camera1" -> 1 or "1" -> 1)
        camera_id_int = self._parse_camera_id(camera_id)
        controller = self._get_controller(camera_id_int)
        controller.continuous_move(x, y, zoom)
        logger.info(
            f"PTZ continuous_move camera={camera_id}, x={x}, y={y}, zoom={zoom}"
        )

    def stop(self, camera_id: str | int) -> Dict[str, Any]:
        """
        Остановить PTZ-движение и вернуть текущий азимут.
        """
        # Convert camera_id string to int (e.g., "camera1" -> 1 or "1" -> 1)
        camera_id_int = self._parse_camera_id(camera_id)
        controller = self._get_controller(camera_id_int)
        controller.stop()
        # по аналогии со старым кодом — после остановки можно сделать restart
        ptz_camera_manager.restart_camera(camera_id_int)
        controller = self._get_controller(camera_id_int)

        azimut = controller.get_azimut()
        logger.info(f"PTZ stop camera={camera_id}, azimut={azimut}")
        return {"status": "ok", "azimut": azimut}

    def set_zoom(self, camera_id: str | int, zoom_delta: float) -> None:
        """
        Изменить зум относительно текущего (zoom_delta может быть отрицательным).
        """
        # Convert camera_id string to int (e.g., "camera1" -> 1 or "1" -> 1)
        camera_id_int = self._parse_camera_id(camera_id)
        controller = self._get_controller(camera_id_int)
        controller.set_zoom(zoom_delta)
        logger.info(f"PTZ set_zoom camera={camera_id}, delta={zoom_delta}")

    def get_status(self, camera_id: str | int) -> Dict[str, Any]:
        """
        Вернуть статус PTZ — пока только азимут.
        Можно расширить, добавив tilt/zoom и т.п.
        """
        # Convert camera_id string to int (e.g., "camera1" -> 1 or "1" -> 1)
        camera_id_int = self._parse_camera_id(camera_id)
        controller = self._get_controller(camera_id_int)
        azimut = controller.get_azimut()
        return {"azimut": azimut}
        # при желании можно вернуть ещё и "сырые" данные:
        # return {"azimut": azimut, "raw": asdict(...)}
        # (если сделаем отдельную dataclass-модель статуса)


ptz_service_instance = PTZService()