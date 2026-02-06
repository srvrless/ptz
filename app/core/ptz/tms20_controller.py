from __future__ import annotations

import time
from typing import Optional

from app.core.ptz.base import BasePTZController
from app.utils.geo import normalize_relative
from logger.setup_logger import get_logger
from app.config.settings import CameraConfig
from app.core.ptz.factory import PTZControllerFactory
from TCP_COMP import (
    Tms20TCP,
)  # файл TCP_COMP.py лежит в корне проекта

logger = get_logger("tms20_controller")

# Состояния zoom для предотвращения спама команд
ZOOM_STATE_STOP = 0
ZOOM_STATE_IN = 1
ZOOM_STATE_OUT = -1


@PTZControllerFactory.register("tms20")
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
        super().__init__(
            cam_lat=cam_lat, cam_lon=cam_lon, cam_h=cam_h, cam_rate=cam_rate
        )

        self.host = host
        self.port = port
        self._tcp = Tms20TCP(ip=host, port=port, pt_addr=pt_addr, cam_addr=cam_addr)
        self._last_azimut: Optional[float] = None

        # Отслеживание состояния zoom чтобы не спамить одинаковые команды
        self._current_zoom_state: int = ZOOM_STATE_STOP

        # Метрики для диагностики
        self._metrics_enabled: bool = False
        self._last_cmd_time: float = 0.0
        self._cmd_count: int = 0
        self._zoom_cmd_count: int = 0

        # Состояние тепловизора
        self._thermal_enabled: bool = False

        try:
            self._tcp.power_on_pt()
            self._tcp.power_on_cam()
            # self._tcp.power_on_ir()  # тепловизор включается вместе с камерой
            # self._thermal_enabled = True
        except Exception as e:
            logger.error(f"TMS-20 power on error: {e}")

    @classmethod
    def from_config(cls, config: CameraConfig) -> "Tms20PTZController":
        """Создать контроллер из конфига камеры."""
        return cls(
            host=config.host,
            port=config.port or 1470,
            cam_lat=config.lat,
            cam_lon=config.lon,
            cam_h=config.height,
            cam_rate=config.rate,
        )

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
        zoom: > 0 — приближение, < 0 — отдаление, = 0 — остановка zoom.
        """
        cmd_start = time.perf_counter()

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
            logger.error(f"TMS-20 continuous_move pan/tilt error: {e}")

        # ====== ZOOM с защитой от спама ======
        # Определяем желаемое состояние zoom
        if zoom > 0:
            desired_zoom_state = ZOOM_STATE_IN
        elif zoom < 0:
            desired_zoom_state = ZOOM_STATE_OUT
        else:
            desired_zoom_state = ZOOM_STATE_STOP

        # Отправляем команду ТОЛЬКО если состояние изменилось
        if desired_zoom_state != self._current_zoom_state:
            try:
                if desired_zoom_state == ZOOM_STATE_IN:
                    self._tcp.zoom_in()
                    self._zoom_cmd_count += 1
                    logger.debug("TMS-20 ZOOM: IN (zoom_cmd=%.3f)", zoom)
                elif desired_zoom_state == ZOOM_STATE_OUT:
                    self._tcp.zoom_out()
                    self._zoom_cmd_count += 1
                    logger.debug("TMS-20 ZOOM: OUT (zoom_cmd=%.3f)", zoom)
                else:  # ZOOM_STATE_STOP
                    self._tcp.zoom_stop()
                    self._zoom_cmd_count += 1
                    logger.debug("TMS-20 ZOOM: STOP (zoom_cmd=%.3f)", zoom)

                self._current_zoom_state = desired_zoom_state
            except Exception as e:
                logger.error(f"TMS-20 zoom command error: {e}")

        # ====== Метрики ======
        cmd_duration = time.perf_counter() - cmd_start
        self._cmd_count += 1

        # Логируем каждые 100 команд или если команда заняла много времени
        if self._cmd_count % 100 == 0 or cmd_duration > 0.05:
            logger.info(
                "TMS-20 METRICS: cmd_count=%d, zoom_cmds=%d, last_cmd_ms=%.1f, "
                "x=%.3f, y=%.3f, zoom=%.3f, zoom_state=%d",
                self._cmd_count, self._zoom_cmd_count, cmd_duration * 1000,
                x, y, zoom, self._current_zoom_state
            )

    def stop(self, pan_tilt: bool = True, zoom: bool = True) -> None:
        try:
            if pan_tilt:
                self._tcp.stop()
            if zoom:
                # Логируем на debug уровне только если состояние менялось
                if self._current_zoom_state != ZOOM_STATE_STOP:
                    logger.debug(
                        "TMS-20 ZOOM: STOP via stop() (prev_state=%d)",
                        self._current_zoom_state
                    )
                self._tcp.zoom_stop()
                self._current_zoom_state = ZOOM_STATE_STOP
        except Exception as e:
            logger.error(f"TMS-20 stop error: {e}")

    def set_zoom(self, delta: float) -> None:
        """
        Относительный зум: delta > 0 — немного приблизить, delta < 0 — отдалить.
        """
        try:
            if delta == 0.0:
                zoom_position = self._tcp.get_zoom_position()
                while zoom_position > 100:
                    zoom_position = self._tcp.get_zoom_position()
                    self._tcp.zoom_out()
                self._tcp.zoom_stop()
            else:
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
