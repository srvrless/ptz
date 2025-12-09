from __future__ import annotations

import time
from typing import Optional

from logger.setup_logger import get_logger

from app.core.ptz.base import BasePTZController
from app.utils.geo import normalize_relative
from TCP_COMP import Tms20TCP  # файл TCP_COMP.py лежит в корне проекта :contentReference[oaicite:0]{index=0}

logger = get_logger("tms20_controller")


class Tms20PTZController(BasePTZController):
    """
    PTZ-контроллер для головы по протоколу TMS-20.
    Использует Tms20TCP под капотом.
    """

    def __init__(
        self,
        host: str,
        port: int,
        cam_lat: float,
        cam_lon: float,
        cam_h: float,
        cam_rate: float,
        pt_addr: int = 0x04,
        cam_addr: int = 0x01,
    ):
        super().__init__(cam_lat=cam_lat, cam_lon=cam_lon, cam_h=cam_h, cam_rate=cam_rate)

        self.host = host
        self.port = port
        self._tcp = Tms20TCP(ip=host, port=port, pt_addr=pt_addr, cam_addr=cam_addr)
        self._last_azimut: Optional[float] = None

        try:
            self._tcp.power_on_pt()
            self._tcp.power_on_cam()
        except Exception as e:
            logger.error(f"TMS-20 power on error: {e}")

    # ---------- реализация абстрактных методов ----------

    def goto_angles(self, az_deg: float, el_deg: float, zoom: Optional[float]) -> None:
        """
        az_deg/el_deg — мировые углы (0 = север, положительное по часовой).
        Переводим в механические пан/тилт и вызываем goto_position.
        """
        mech_pan = normalize_relative(az_deg - self.cam_rate)
        mech_pan = max(-179.99, min(180.0, mech_pan))
        mech_tilt = max(-70.0, min(45.0, el_deg))

        try:
            self._tcp.goto_position(pan_deg=mech_pan, tilt_deg=mech_tilt)
            self._last_azimut = az_deg
        except Exception as e:
            logger.error(f"TMS-20 goto_position error: {e}")

        # zoom: здесь протокол даёт только Tele/Wide/Stop;
        # если нужно, можно доработать работу с zoom.

    def continuous_move(self, x: float, y: float, zoom: float = 0.0) -> None:
        """
        x, y в [-1, 1] → скорость 0..63 по протоколу.
        """
        def speed(v: float) -> int:
            return max(0, min(63, int(abs(v) * 63)))

        try:
            if x == 0 and y == 0:
                self._tcp.stop()
            elif x > 0 and y == 0:
                self._tcp.move_right(speed(x))
            elif x < 0 and y == 0:
                self._tcp.move_left(speed(x))
            elif x == 0 and y > 0:
                self._tcp.move_up(speed(y))
            elif x == 0 and y < 0:
                self._tcp.move_down(speed(y))
            elif x > 0 and y > 0:
                self._tcp.move_up_right(speed(x), speed(y))
            elif x < 0 and y > 0:
                self._tcp.move_up_left(speed(x), speed(y))
            elif x > 0 and y < 0:
                self._tcp.move_down_right(speed(x), speed(y))
            elif x < 0 and y < 0:
                self._tcp.move_down_left(speed(x), speed(y))
        except Exception as e:
            logger.error(f"TMS-20 continuous_move error: {e}")

        # zoom управление (по желанию):
        if zoom != 0:
            try:
                if zoom > 0:
                    self._tcp.zoom_in()
                else:
                    self._tcp.zoom_out()
            except Exception as e:
                logger.error(f"TMS-20 zoom move error: {e}")

    def stop(self, pan_tilt: bool = True, zoom: bool = True) -> None:
        try:
            if pan_tilt:
                self._tcp.stop()
            if zoom:
                self._tcp.zoom_stop()
        except Exception as e:
            logger.error(f"TMS-20 stop error: {e}")

    def set_zoom(self, delta: float) -> None:
        """
        Относительный зум: delta > 0 — немного приблизить, delta < 0 — отдалить.
        """
        try:
            if delta > 0:
                self._tcp.zoom_in()
            elif delta < 0:
                self._tcp.zoom_out()
            else:
                return

            time.sleep(0.2 * abs(delta))
            self._tcp.zoom_stop()
        except Exception as e:
            logger.error(f"TMS-20 set_zoom error: {e}")

    def get_azimut(self) -> Optional[float]:
        """
        Протокол статуса не даёт, поэтому возвращаем последний целевой азимут.
        """
        return self._last_azimut
