from __future__ import annotations

from typing import Optional

from onvif import ONVIFCamera

from logger.setup_logger import get_logger
from app.utils.geo import normalize_deg
from app.core.ptz.base import BasePTZController

logger = get_logger("ptz_controller")

MAX_TILT_ANGLE = 45.0  # максимально допустимый угол места в градусах


class PTZController(BasePTZController):
    """
    ONVIF PTZ-контроллер.
    Работает в абсолютных координатах GenericSpace [-1, 1].
    """

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        port: int,
        cam_rate: float,
        cam_lat: float,
        cam_lon: float,
        cam_h: float,
        wsdl_dir: Optional[str] = None,
    ):
        super().__init__(cam_lat=cam_lat, cam_lon=cam_lon, cam_h=cam_h, cam_rate=cam_rate)

        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.wsdl_dir = wsdl_dir

        self.camera: Optional[ONVIFCamera] = None
        self.media = None
        self.ptz = None
        self.profile = None
        self.status = None

        self._connect()

    # ---------- подключение ----------

    def _connect(self) -> None:
        try:
            if self.wsdl_dir:
                self.camera = ONVIFCamera(self.host, self.port, self.user, self.password, self.wsdl_dir)
            else:
                self.camera = ONVIFCamera(self.host, self.port, self.user, self.password)

            self.media = self.camera.create_media_service()
            self.ptz = self.camera.create_ptz_service()

            profiles = self.media.GetProfiles()
            self.profile = profiles[0]

            self.status = self.ptz.GetStatus({"ProfileToken": self.profile.token})
            logger.info(f"PTZController подключён к {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Ошибка подключения к PTZ-камере {self.host}:{self.port}: {e}")
            self.camera = None
            self.media = None
            self.ptz = None
            self.profile = None
            self.status = None

    def _refresh_status(self) -> None:
        if not self.ptz or not self.profile:
            return
        try:
            self.status = self.ptz.GetStatus({"ProfileToken": self.profile.token})
        except Exception as e:
            logger.error(f"Ошибка получения статуса PTZ: {e}")

    # ---------- вспомогательные преобразования ----------

    def get_azimut(self) -> Optional[float]:
        """
        Текущий азимут камеры в градусах [0, 360) с учётом cam_rate.
        Переводит pan [-1,1] в градусы.
        """
        self._refresh_status()
        if not self.status:
            return None
        try:
            pan_x = self.status.Position.PanTilt.x  # [-1..1]
        except Exception as e:
            logger.error(f"Не удалось получить pan из статуса PTZ: {e}")
            return None

        # -1 -> 0°, 1 -> 360°
        mechanical_deg = (pan_x + 1.0) * 180.0
        world_az = normalize_deg(mechanical_deg + self.cam_rate)
        return world_az

    def _normalize_to_onvif_pan(self, world_azimuth_deg: float) -> float:
        """
        Перевод мирового азимута (0..360) в ONVIF pan [-1, 1].
        """
        mechanical_deg = normalize_deg(world_azimuth_deg - self.cam_rate)
        x = mechanical_deg / 180.0 - 1.0  # 0° -> -1, 180° -> 0, 360° -> 1
        return max(-1.0, min(1.0, x))

    def _normalize_to_onvif_tilt(self, elevation_deg: float) -> float:
        """
        Перевод elevation в ONVIF tilt [-1, 1].
        """
        clamped = max(-MAX_TILT_ANGLE, min(MAX_TILT_ANGLE, elevation_deg))
        return clamped / MAX_TILT_ANGLE

    # ---------- базовые операции PTZ ----------

    def move(self, x: float, y: float, zoom: Optional[float] = None) -> None:
        """
        Абсолютное перемещение в координатах ONVIF [-1..1].
        """
        if not self.ptz or not self.profile:
            logger.error("PTZ-сервис не инициализирован")
            return

        try:
            self._refresh_status()
            request = self.ptz.create_type("AbsoluteMove")
            request.ProfileToken = self.profile.token
            request.Position = self.status.Position

            request.Position.PanTilt.x = max(-1.0, min(1.0, x))
            request.Position.PanTilt.y = max(-1.0, min(1.0, y))

            if zoom is not None:
                request.Position.Zoom.x = max(0.0, min(1.0, zoom))
            else:
                # Если не задаём zoom — оставляем текущий
                request.Position.Zoom.x = self.status.Position.Zoom.x

            self.ptz.AbsoluteMove(request)
            self._refresh_status()
        except Exception as e:
            logger.error(f"PTZ AbsoluteMove error: {e}")

    def continuous_move(self, x: float, y: float, zoom: float = 0.0) -> None:
        if not self.ptz or not self.profile:
            logger.error("PTZ-сервис не инициализирован")
            return

        try:
            self._refresh_status()
            request = self.ptz.create_type("ContinuousMove")
            request.ProfileToken = self.profile.token

            request.Velocity = self.status.Position
            request.Velocity.PanTilt.x = max(-1.0, min(1.0, x))
            request.Velocity.PanTilt.y = max(-1.0, min(1.0, y))
            request.Velocity.Zoom.x = max(-1.0, min(1.0, zoom))

            self.ptz.ContinuousMove(request)
        except Exception as e:
            logger.error(f"PTZ continuous_move error: {e}")

    def stop(self, pan_tilt: bool = True, zoom: bool = True) -> None:
        if not self.ptz or not self.profile:
            logger.error("PTZ-сервис не инициализирован")
            return

        try:
            request = self.ptz.create_type("Stop")
            request.ProfileToken = self.profile.token
            request.PanTilt = pan_tilt
            request.Zoom = zoom
            self.ptz.Stop(request)
        except Exception as e:
            logger.error(f"PTZ stop error: {e}")

    def set_zoom(self, delta: float) -> None:
        """
        Изменить зум относительно текущего.
        delta > 0 — приблизить, delta < 0 — отдалить.
        """
        if not self.ptz or not self.profile:
            logger.error("PTZ-сервис не инициализирован")
            return

        self._refresh_status()
        try:
            current = getattr(self.status.Position.Zoom, "x", 0.0) or 0.0
            new_zoom = max(0.0, min(1.0, current + delta))

            request = self.ptz.create_type("AbsoluteMove")
            request.ProfileToken = self.profile.token
            request.Position = self.status.Position
            request.Position.Zoom.x = new_zoom

            self.ptz.AbsoluteMove(request)
            self._refresh_status()
        except Exception as e:
            logger.error(f"PTZ set_zoom error: {e}")

    # ---------- реализация абстрактного goto_angles ----------

    def goto_angles(self, az_deg: float, el_deg: float, zoom: Optional[float]) -> None:
        pan_x = self._normalize_to_onvif_pan(az_deg)
        tilt_y = self._normalize_to_onvif_tilt(el_deg)
        self.move(pan_x, tilt_y, zoom)
