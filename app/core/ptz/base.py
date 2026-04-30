from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from app.utils.geo import azimuth_from_latlon, elevation_from_latlon


class BasePTZController(ABC):
    """
    Общий интерфейс для всех PTZ-контроллеров (ONVIF, TMS-20 и т.д.).
    """

    def __init__(
        self,
        cam_lat: float,
        cam_lon: float,
        cam_h: float,
        cam_rate: float,
    ):
        self.cam_latlon: Tuple[float, float] = (cam_lat, cam_lon)
        self.cam_h = cam_h
        self.cam_rate = cam_rate

    # --- низкоуровневые действия, специфичные для конкретного протокола ---

    @abstractmethod
    def goto_angles(self, az_deg: float, el_deg: float, zoom: Optional[float]) -> None:
        """
        Навести камеру на заданные азимут/угол места в градусах мира (0 = север).
        """

    @abstractmethod
    def continuous_move(self, x: float, y: float, zoom: float = 0.0) -> None: ...

    @abstractmethod
    def stop(self, pan_tilt: bool = True, zoom: bool = True) -> None: ...

    @abstractmethod
    def set_zoom(self, delta: float) -> None: ...

    @abstractmethod
    def get_azimut(self) -> Optional[float]:
        """
        Текущий азимут в градусах (0..360) или None, если недоступен.
        """

    # --- общий high-level: наведение по координатам ---

    def search_target(
        self,
        target_lat: float,
        target_lon: float,
        target_h: float,
        radar_h: float,
        zoom: Optional[float] = None,
    ) -> Optional[float]:
        """
        Общая логика: считаем азимут/elevation и вызываем goto_angles.
        Возвращает целевой азимут (в градусах мира) или None.
        """
        if self.cam_latlon is None or self.cam_h is None:
            return None
        target_az = azimuth_from_latlon(
            self.cam_latlon, (target_lat, target_lon), self.cam_rate
        )
        target_el = elevation_from_latlon(
            self.cam_latlon,
            self.cam_h,
            (target_lat, target_lon),
            target_h,
            radar_h,
        )

        self.goto_angles(target_az, target_el, zoom)
        return target_az
