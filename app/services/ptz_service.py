from __future__ import annotations

from typing import Any, Dict, Optional

from app.config.settings import AppConfig, CameraConfig
from app.core.ptz.controller import PTZController
from app.core.ptz.manager import PTZCameraManager
from app.exceptions import CameraNotFoundError, PTZControllerNotFoundError, PTZMoveError
from logger.setup_logger import get_logger
from app.schemas.camera import CameraResponse, ConnectionResponse, LocationResponse
from app.services.camera_gateway_client import CameraGatewayClient


logger = get_logger("ptz_service")


class PTZService:
    """
    Сервисный слой для управления PTZ-камерами.
    Конфиг запрашивается из БД только при первом обращении к камере (select / первый PTZ).
    Дальше используется кэш в PTZCameraManager — без доп. запросов к БД.
    """

    def __init__(
        self,
        ptz_manager: PTZCameraManager,
        config: AppConfig,
        camera_gateway: CameraGatewayClient,
    ):
        self._ptz_manager = ptz_manager
        self.config = config
        self._camera_gateway = camera_gateway

    def _fetch_camera_config_from_api(self, camera_id: int) -> CameraConfig:
        """Запрос конфига из БД. Конвертация внутри with — объект не detached."""
        camera_cfg = self._camera_gateway.get_camera_config_by_id(camera_id)
        if camera_cfg is None:
            logger.warning(f"Camera not found in API: {camera_id}")
            raise PTZControllerNotFoundError(str(camera_id))
        return camera_cfg

    def _get_controller(self, camera_id: int) -> PTZController:
        """Контроллер из кэша. При первом обращении — запрос в БД и init_camera."""
        if not self._ptz_manager.is_initialized(camera_id):
            cam_cfg = self._fetch_camera_config_from_api(camera_id)
            self._ptz_manager.init_camera(camera_id, cam_cfg)
        return self._ptz_manager.get_controller(camera_id)

    def _get_radar_height(self, radar_id: int) -> float:
        try:
            return self.config.heights[radar_id]
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
            self._ptz_manager.restart_controller(camera_id)

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
            raise PTZMoveError(camera_id=camera_id, reason="target_az is None")

        logger.info(f"PTZ {camera_id} moved to azimuth {target_az:.2f}")
        return {"status": "ok", "azimut": float(target_az)}

    def move_to_target_with_excluded_cameras(
        self,
        *,
        excluded_cameras_id: list[int] | None,
        lat: float,
        lon: float,
        height: float,
        zoom: Optional[float] = None,
        radar_id: int = 1,
        restart_before_move: bool = True,
    ) -> Dict[str, Any]:
        """
        Выбирает ближайшую камеру и наводит её на цель по гео-координатам
        Возвращает CameraResponse? с результатом:
        { "camera": CameraResponse, "azimut": <float> }

        Бросает:
          - PTZControllerNotFoundError
          - PTZMoveError
          - ValueError (если radar_id некорректен)
        """
        best_cam_cfg = self._camera_gateway.get_nearest_camera_config(
            lat=lat, lon=lon, excluded_cameras_id=excluded_cameras_id
        )
        if best_cam_cfg is None:
            raise CameraNotFoundError("nearest_camera")

        camera_id = best_cam_cfg.id
        camera_response = CameraResponse(
            id=best_cam_cfg.id,
            name=best_cam_cfg.name,
            connection=ConnectionResponse(
                rtsp_url=best_cam_cfg.rtsp_url,
                rtsp_url_ik=best_cam_cfg.rtsp_url_ik,
            ),
            location=LocationResponse(lat=best_cam_cfg.lat, lon=best_cam_cfg.lon),
        )
        radar_h = self._get_radar_height(radar_id)
        if restart_before_move:
            controller = self._ptz_manager.restart_controller(camera_id)

        target_az = controller.search_target(
            target_lat=lat,
            target_lon=lon,
            target_h=height,
            radar_h=radar_h,
            zoom=zoom,
        )
        if target_az is None:
            logger.error(f"PTZ move_to_target failed for {camera_id}")
            raise PTZMoveError(camera_id=camera_id, reason="target_az is None")

        logger.info(f"PTZ {camera_id} moved to azimuth {target_az:.2f}")
        return {"camera": camera_response, "azimut": float(target_az)}

    def continuous_move(
        self,
        camera_id: int,
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
        self._ptz_manager.restart_controller(camera_id)
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

    def get_status(self, camera_id: int) -> Dict[str, Any]:
        """
        Вернуть статус PTZ — пока только азимут.
        Можно расширить, добавив tilt/zoom и т.п.
        """
        controller = self._get_controller(camera_id)
        azimut = controller.get_azimut()
        return {"azimut": azimut}
        # при желании можно вернуть ещё и "сырые" данные:
        # return {"azimut": azimut, "raw": asdict(...)}
        # (если сделаем отдельную datacl    ass-модель статуса)
