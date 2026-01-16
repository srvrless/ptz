from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from logger.setup_logger import get_logger

from app.config.settings import config
from app.core.ptz.manager import ptz_camera_manager
from app.core.ptz.controller import PTZController

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
            raise PTZControllerNotFoundError(f"PTZController not found for camera {camera_id}")
        return controller

    def _get_radar_height(self, radar_id: int) -> float:
        try:
            return config.heights[radar_id - 1]
        except IndexError:
            raise ValueError(f"Invalid radar_id: {radar_id}")

    # ---------- high-level операции ----------

    def move_to_target(
        self,
        camera_id: int,
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
        radar_h = self._get_radar_height(radar_id)

        if restart_before_move:
            logger.info(f"Restart PTZ controller before move: {camera_id}")
            ptz_camera_manager.restart_camera(camera_id)

        controller = self._get_controller(camera_id)

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
        camera_id: str,
        *,
        x: float,
        y: float,
        zoom: float = 0.0,
    ) -> None:
        """
        Непрерывное движение PTZ.
        x, y, zoom — скорости в диапазоне [-1, 1].
        """
        controller = self._get_controller(camera_id)
        controller.continuous_move(x, y, zoom)
        logger.info(
            f"PTZ continuous_move camera={camera_id}, x={x}, y={y}, zoom={zoom}"
        )

    def stop(self, camera_id: int) -> Dict[str, Any]:
        """
        Остановить PTZ-движение и вернуть текущий азимут.
        """
        controller = self._get_controller(camera_id)
        controller.stop()
        # по аналогии со старым кодом — после остановки можно сделать restart
        ptz_camera_manager.restart_camera(camera_id)
        controller = self._get_controller(camera_id)

        azimut = controller.get_azimut()
        logger.info(f"PTZ stop camera={camera_id}, azimut={azimut}")
        return {"status": "ok", "azimut": azimut}

    def set_zoom(self, camera_id: int, zoom_delta: float) -> None:
        """
        Изменить зум относительно текущего (zoom_delta может быть отрицательным).
        """
        controller = self._get_controller(camera_id)
        controller.set_zoom(zoom_delta)
        logger.info(f"PTZ set_zoom camera={camera_id}, delta={zoom_delta}")

    def get_status(self, camera_id: str) -> Dict[str, Any]:
        """
        Вернуть статус PTZ — пока только азимут.
        Можно расширить, добавив tilt/zoom и т.п.
        """
        controller = self._get_controller(camera_id)
        azimut = controller.get_azimut()
        return {"azimut": azimut}
        # при желании можно вернуть ещё и "сырые" данные:
        # return {"azimut": azimut, "raw": asdict(...)}
        # (если сделаем отдельную dataclass-модель статуса)
        

ptz_service = PTZService()
