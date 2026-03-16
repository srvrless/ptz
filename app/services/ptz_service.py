from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.config.settings import AppConfig, CameraConfig
from app.core.ptz.controller import PTZController
from app.core.ptz.manager import PTZCameraManager
from app.exceptions import CameraNotFoundError, PTZMoveError
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

    def _assert_owned(self, camera_id: int, client_id: str) -> None:
        """Ownership проверяем локально, без gateway."""
        self._ptz_manager.assert_owner(camera_id, client_id)

    def _get_controller(self, camera_id: int) -> PTZController:
        """
        Контроллер из кэша.
        Создаётся при select_camera (CameraService) — здесь gateway не дергаем.
        """
        try:
            return self._ptz_manager.get_controller(camera_id)  # type: ignore[return-value]
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail="Камера не инициализирована. Сначала вызовите select_camera.",
            ) from exc

    def _get_radar_height(self, radar_id: int) -> float:
        try:
            return self.config.heights[radar_id]
        except IndexError:
            raise ValueError(f"Invalid radar_id: {radar_id}")

    # ---------- high-level операции ----------

    def move_to_target(
        self,
        camera_id: int,
        client_id: str,
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
          - PTZMoveError`
          - ValueError (если radar_id некорректен)
        """
        self._assert_owned(camera_id, client_id)
        if restart_before_move:
            logger.info(f"Restart PTZ controller before move: {camera_id}")
            self._ptz_manager.restart_controller(camera_id)

        controller = self._get_controller(camera_id)

        radar_h = self._get_radar_height(radar_id)
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
        client_id: str,
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
        best_cam_cfg = self._camera_gateway.get_nearest_camera_config(lat=lat, lon=lon)
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

        # `move_to_target` вызывается раз в несколько секунд — обращение к gateway
        # тут допустимо, чтобы узнать "лучшее свободное" устройство.
        # Ownership/claim/release здесь не трогаем: перед `move_to_target` всегда
        # вызывается `select_camera`, который поднимет контроллер и зафиксирует owner.
        result = self.move_to_target(
            camera_id=camera_id,
            client_id=client_id,
            lat=lat,
            lon=lon,
            height=height,
            zoom=zoom,
            radar_id=radar_id,
            restart_before_move=restart_before_move,
        )
        return {"camera": camera_response, "azimut": result["azimut"]}

    def continuous_move(
        self,
        camera_id: int,
        client_id: str,
        *,
        x: float,
        y: float,
        zoom: float = 0.0,
    ) -> None:
        """
        Непрерывное движение PTZ.
        x, y, zoom — скорости в диапазоне [-1, 1].
        """
        self._assert_owned(camera_id, client_id)
        controller = self._get_controller(camera_id)
        controller.continuous_move(x, y, zoom)
        logger.info(
            f"PTZ continuous_move camera={camera_id}, x={x}, y={y}, zoom={zoom}"
        )

    def stop(self, camera_id: int, *, client_id: str) -> Dict[str, Any]:
        """
        Остановить PTZ-движение и вернуть текущий азимут.
        """
        self._assert_owned(camera_id, client_id)
        controller = self._get_controller(camera_id)
        controller.stop()
        # по аналогии со старым кодом — после остановки можно сделать restart
        self._ptz_manager.restart_controller(camera_id)
        controller = self._get_controller(camera_id)

        azimut = controller.get_azimut()
        logger.info(f"PTZ stop camera={camera_id}, azimut={azimut}")
        return {"status": "ok", "azimut": azimut}

    def set_zoom(self, camera_id: int, *, client_id: str, zoom_delta: float) -> None:
        """
        Изменить зум относительно текущего (zoom_delta может быть отрицательным).
        """
        self._assert_owned(camera_id, client_id)
        controller = self._get_controller(camera_id)
        controller.set_zoom(zoom_delta)
        logger.info(f"PTZ set_zoom camera={camera_id}, delta={zoom_delta}")

    def get_status(self, camera_id: int, *, client_id: str) -> Dict[str, Any]:
        """
        Вернуть статус PTZ — пока только азимут.
        Можно расширить, добавив tilt/zoom и т.п.
        """
        self._assert_owned(camera_id, client_id)
        controller = self._get_controller(camera_id)
        azimut = controller.get_azimut()
        return {"azimut": azimut}
        # при желании можно вернуть ещё и "сырые" данные:
        # return {"azimut": azimut, "raw": asdict(...)}
        # (если сделаем отдельную datacl    ass-модель статуса)
