from __future__ import annotations

import time
from typing import Optional

from onvif import ONVIFCamera
from zeep.transports import Transport
from requests import Session
from requests.exceptions import RequestException
from app.core.ptz.base import BasePTZController
from app.core.ptz.factory import PTZControllerFactory
from app.utils.geo import normalize_deg
from app.config.settings import CameraConfig
from logger.setup_logger import get_logger

logger = get_logger("ptz_controller")

MAX_TILT_ANGLE = 45.0  # максимально допустимый угол места в градусах

# Состояния zoom для предотвращения спама команд
ZOOM_STATE_STOP = 0
ZOOM_STATE_IN = 1
ZOOM_STATE_OUT = -1


@PTZControllerFactory.register("onvif")
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
        zoom_speed: float = 0.3,
    ):
        super().__init__(
            cam_lat=cam_lat, cam_lon=cam_lon, cam_h=cam_h, cam_rate=cam_rate
        )

        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.wsdl_dir = wsdl_dir
        self._zoom_speed = max(0.0, min(1.0, zoom_speed))

        self.camera: Optional[ONVIFCamera] = None
        self.media = None
        self.ptz = None
        self.profile = None
        self.status = None

        # Отслеживание состояния zoom чтобы не спамить одинаковые команды
        self._current_zoom_state: int = ZOOM_STATE_STOP

        # Кэш статуса чтобы не делать сетевой запрос на каждый вызов continuous_move
        self._status_cache_time: float = 0.0
        self._status_cache_ttl: float = 1.0  # Обновлять статус не чаще раза в секунду

        # Метрики для диагностики
        self._cmd_count: int = 0
        self._zoom_cmd_count: int = 0

        self._connect()

    @classmethod
    def from_config(cls, config: CameraConfig) -> "PTZController":
        """Создать контроллер из конфига камеры."""
        return cls(
            host=config.host,
            user=config.user,
            password=config.password,
            port=config.port,
            cam_rate=config.rate,
            cam_lat=config.lat,
            cam_lon=config.lon,
            cam_h=config.height,
        )

    # ---------- подключение ----------

    def _connect(self):
        session = Session()
        timeout = 5
        transport = Transport(session=session, timeout=timeout)

        try:
            # 3. Передаем transport в ONVIFCamera
            if self.wsdl_dir:
                self.camera = ONVIFCamera(
                    self.host, self.port, self.user, self.password, 
                    self.wsdl_dir, transport=transport
                )
            else:
                self.camera = ONVIFCamera(
                    self.host, self.port, self.user, self.password, 
                    transport=transport
                )
            
            # 4. Выполняем действия, которые реально обращаются к сети
            self.media = self.camera.create_media_service()
            self.ptz = self.camera.create_ptz_service()

            # Первый сетевой запрос (именно здесь сработает таймаут, если камера не отвечает)
            profiles = self.media.GetProfiles()
            if not profiles:
                raise Exception("Профили не найдены")
                
            self.profile = profiles[0]
            self.status = self.ptz.GetStatus({"ProfileToken": self.profile.token})
            
            logger.info(f"Успешное подключение к {self.host}")

        except (RequestException, Exception) as e:
            self.camera = None
            self.media = None
            self.ptz = None
            self.profile = None
            self.status = None

            # Логируем и пробрасываем исключение дальше (raise), 
            # чтобы внешний код мог сделать retry
            logger.error(f"Ошибка при подключении к {self.host}: {e}")
            raise

    def _refresh_status(self, force: bool = False) -> None:
        """
        Обновить статус камеры.
        Используется кэширование чтобы не делать сетевые запросы слишком часто.
        force=True — принудительно обновить игнорируя кэш.
        """
        if not self.ptz or not self.profile:
            return

        now = time.monotonic()
        if not force and (now - self._status_cache_time) < self._status_cache_ttl:
            return  # Используем кэшированный статус

        try:
            self.status = self.ptz.GetStatus({"ProfileToken": self.profile.token})
            self._status_cache_time = now
        except Exception as e:
            logger.error(f"Ошибка получения статуса PTZ: {e}")

    # ---------- вспомогательные преобразования ----------

    def get_azimut(self) -> Optional[float]:
        """
        Текущий азимут камеры в градусах [0, 360) с учётом cam_rate.
        Переводит pan [-1,1] в градусы.
        """
        self._refresh_status(force=True)  # Нужен актуальный статус
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
            self._refresh_status(force=True)  # Нужен актуальный статус для позиции
            request = self.ptz.create_type("AbsoluteMove")
            request.ProfileToken = self.profile.token
            request.Position = self.status.Position

            request.Position.PanTilt.x = max(-1.0, min(1.0, x))
            request.Position.PanTilt.y = max(-1.0, min(1.0, y))

            if zoom is not None:
                request.Position.Zoom.x = self.status.Position.Zoom.x
            else:
                # Если не задаём zoom — оставляем текущий
                request.Position.Zoom.x = self.status.Position.Zoom.x

            self.ptz.AbsoluteMove(request)
            self._refresh_status(force=True)
        except Exception as e:
            logger.error(f"PTZ AbsoluteMove error: {e}")

    def continuous_move(self, x: float, y: float, zoom: float = 0.0) -> None:
        """
        Непрерывное движение камеры.
        x, y: скорость pan/tilt [-1, 1]
        zoom: скорость zoom [-1, 1], где >0 = zoom in, <0 = zoom out, 0 = stop

        Оптимизации:
        - Кэширование статуса (не запрашивать при каждом вызове)
        - Отслеживание состояния zoom (логирование изменений)
        """
        if not self.ptz or not self.profile:
            logger.error("PTZ-сервис не инициализирован")
            return

        self._cmd_count += 1

        # Определяем желаемое состояние zoom для логирования
        if zoom > 0:
            desired_zoom_state = ZOOM_STATE_IN
        elif zoom < 0:
            desired_zoom_state = ZOOM_STATE_OUT
        else:
            desired_zoom_state = ZOOM_STATE_STOP

        # Логируем изменения состояния zoom
        if desired_zoom_state != self._current_zoom_state:
            self._zoom_cmd_count += 1
            if desired_zoom_state == ZOOM_STATE_IN:
                logger.debug("ONVIF ZOOM: IN (zoom=%.3f)", zoom)
            elif desired_zoom_state == ZOOM_STATE_OUT:
                logger.debug("ONVIF ZOOM: OUT (zoom=%.3f)", zoom)
            else:
                logger.debug("ONVIF ZOOM: STOP")
            self._current_zoom_state = desired_zoom_state

        try:
            # Используем кэшированный статус (обновляется не чаще раза в секунду)
            self._refresh_status()

            request = self.ptz.create_type("ContinuousMove")
            request.ProfileToken = self.profile.token

            request.Velocity = self.status.Position
            request.Velocity.PanTilt.x = max(-1.0, min(1.0, x))
            request.Velocity.PanTilt.y = max(-1.0, min(1.0, y))
            scaled_zoom = zoom * self._zoom_speed
            request.Velocity.Zoom.x = max(-1.0, min(1.0, scaled_zoom))

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

            # Обновляем состояние zoom
            if zoom and self._current_zoom_state != ZOOM_STATE_STOP:
                logger.debug(
                    "ONVIF ZOOM: STOP via stop() (prev_state=%d)",
                    self._current_zoom_state,
                )
                self._current_zoom_state = ZOOM_STATE_STOP
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

        self._refresh_status(force=True)  # Нужен актуальный статус для текущего zoom
        try:
            current = getattr(self.status.Position.Zoom, "x", 0.0) or 0.0
            scaled_delta = delta * self._zoom_speed
            new_zoom = max(0.0, min(1.0, current + scaled_delta))

            request = self.ptz.create_type("AbsoluteMove")
            request.ProfileToken = self.profile.token
            request.Position = self.status.Position
            if delta == 0.0:
                request.Position.Zoom.x = 0.0
            else:
                request.Position.Zoom.x = new_zoom

            self.ptz.AbsoluteMove(request)
            self._refresh_status(force=True)
        except Exception as e:
            logger.error(f"PTZ set_zoom error: {e}")

    # ---------- реализация абстрактного goto_angles ----------

    def goto_angles(self, az_deg: float, el_deg: float, zoom: Optional[float]) -> None:
        pan_x = self._normalize_to_onvif_pan(az_deg)
        tilt_y = self._normalize_to_onvif_tilt(el_deg)
        self.move(pan_x, tilt_y, zoom)
