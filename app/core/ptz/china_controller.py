from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.config.settings import CameraConfig
from app.core.ptz.base import BasePTZController
from app.core.ptz.factory import PTZControllerFactory
from app.utils.geo import normalize_deg
from logger.setup_logger import get_logger

logger = get_logger("china_controller")

DEFAULT_HTTP_PORT = 8080
DEFAULT_TIMEOUT_SECONDS = 3.0
DEFAULT_USER_ID = 1000
DEFAULT_MOVE_SPEED = 30
DEFAULT_ZOOM_SPEED = 30
DEFAULT_CONTINUOUS_STEP_DEG = 3.0

MIN_ELEVATION_DEG = -90.0
MAX_ELEVATION_DEG = 90.0
MIN_ZOOM_POSITION = 1.0


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _clamp_speed(speed: int) -> int:
    return int(max(1, min(100, speed)))


def _base_url_from_host(host: str, port: int) -> str:
    """
    Собирает base_url для China HTTP API.

    Поддерживаем оба варианта конфига:
    - host="127.0.0.1", port=8080 -> http://127.0.0.1:8080/api/
    - host="http://127.0.0.1:18080/api" -> http://127.0.0.1:18080/api/
    """
    raw_host = host.strip().rstrip("/")
    if not raw_host:
        raise ValueError("China host is empty")

    if "://" not in raw_host:
        if "/" in raw_host:
            netloc, raw_path = raw_host.split("/", 1)
            path = f"/{raw_path.strip('/')}"
        else:
            netloc = raw_host
            path = ""

        if ":" not in netloc:
            netloc = f"{netloc}:{port}"

        path = path.rstrip("/")
        if not path:
            path = "/api"
        elif not path.endswith("/api"):
            path = f"{path}/api"

        return f"http://{netloc}{path}/"

    parsed = urlsplit(raw_host)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/api"
    elif not path.endswith("/api"):
        path = f"{path}/api"

    netloc = parsed.netloc
    if parsed.port is None and port and ":" not in netloc:
        netloc = f"{netloc}:{port}"

    return urlunsplit((parsed.scheme, netloc, f"{path}/", "", ""))


def _user_id_from_config(config: CameraConfig) -> int:
    """
    В протоколе China требуется numeric user_id.
    В наших конфигах отдельного поля под него пока нет, поэтому берём первый
    числовой идентификатор из client_id/user, иначе используем дефолт из документации.
    """
    for value in (config.client_id, config.user):
        if value is None:
            continue
        value_str = str(value).strip()
        if value_str.isdigit():
            return int(value_str)
    return DEFAULT_USER_ID


@PTZControllerFactory.register("china")
class ChinaPTZController(BasePTZController):
    """
    PTZ-контроллер для China HTTP API.

    Документация описывает только абсолютные команды:
    - POST /ptz/move/absolute
    - POST /ptz/zoom/absolute

    Поэтому continuous_move эмулируется короткими абсолютными смещениями, а stop()
    является no-op для pan/tilt: отдельного endpoint остановки в протоколе нет.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        device_id: int,
        user_id: int,
        cam_lat: float,
        cam_lon: float,
        cam_h: float,
        cam_rate: float,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        move_speed: int = DEFAULT_MOVE_SPEED,
        zoom_speed: int = DEFAULT_ZOOM_SPEED,
        continuous_step_deg: float = DEFAULT_CONTINUOUS_STEP_DEG,
    ) -> None:
        super().__init__(
            cam_lat=cam_lat,
            cam_lon=cam_lon,
            cam_h=cam_h,
            cam_rate=cam_rate,
        )

        self.device_id = int(device_id)
        self.user_id = int(user_id)
        self._move_speed = _clamp_speed(move_speed)
        self._zoom_speed = _clamp_speed(zoom_speed)
        self._continuous_step_deg = max(0.1, float(continuous_step_deg))

        self._last_azimut: Optional[float] = None
        self._last_elevation: float = 0.0
        self._zoom_position: float = MIN_ZOOM_POSITION

        self.base_url = _base_url_from_host(host, port)
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        logger.info(
            "China PTZ controller initialized: device_id=%s base_url=%s user_id=%s",
            self.device_id,
            self.base_url,
            self.user_id,
        )

    @classmethod
    def from_config(cls, config: CameraConfig) -> "ChinaPTZController":
        """Создать контроллер из конфига камеры."""
        port = config.port
        if port in (0, 554):
            # 554 остаётся дефолтом CameraConfig для RTSP/ONVIF, но China HTTP API
            # по документации слушает 8080 в production и 18080 в development.
            port = DEFAULT_HTTP_PORT

        return cls(
            host=config.host,
            port=port,
            device_id=config.id,
            user_id=_user_id_from_config(config),
            cam_lat=config.lat,
            cam_lon=config.lon,
            cam_h=config.height,
            cam_rate=config.rate,
            zoom_speed=int(round(config.zoom_speed * 100)),
        )

    # ---------- HTTP helpers ----------

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(endpoint, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "China request failed: endpoint=%s payload=%s error=%s",
                endpoint,
                payload,
                exc,
            )
            raise

        try:
            data = response.json()
        except ValueError:
            data = {}

        business_code = data.get("code")
        if business_code not in (None, 0, 200):
            raise RuntimeError(
                f"China API returned business error: endpoint={endpoint}, response={data}"
            )

        return data

    def _move_absolute(self, az_deg: float, el_deg: float) -> None:
        pan = normalize_deg(az_deg)
        elevation = _clamp(el_deg, MIN_ELEVATION_DEG, MAX_ELEVATION_DEG)

        # В WebSocket-статусе pitch описан как [-90..90], а HTTP tilt — как [0..180].
        # Используем стандартное смещение: -90 -> 0, 0 -> 90, +90 -> 180.
        tilt = elevation + 90.0

        payload = {
            "id": self.device_id,
            "user_id": self.user_id,
            "pan": round(pan, 3),
            "tilt": round(tilt, 3),
            "speed": self._move_speed,
        }
        self._post("ptz/move/absolute", payload)

        self._last_azimut = pan
        self._last_elevation = elevation

    def _zoom_absolute(self, position: float) -> None:
        position = max(MIN_ZOOM_POSITION, float(position))
        payload = {
            "id": self.device_id,
            "user_id": self.user_id,
            "position": round(position, 3),
            "speed": self._zoom_speed,
        }
        self._post("ptz/zoom/absolute", payload)
        self._zoom_position = position

    # ---------- BasePTZController implementation ----------

    def goto_angles(self, az_deg: float, el_deg: float, zoom: Optional[float]) -> None:
        """
        Навести камеру по мировому азимуту/углу места.

        China API по документации оперирует yaw/pan в мировых градусах
        (0 = North, clockwise), поэтому cam_rate здесь не вычитаем.
        """
        self._move_absolute(az_deg, el_deg)
        if zoom is not None and zoom > 0:
            self._zoom_absolute(zoom)

    def continuous_move(self, x: float, y: float, zoom: float = 0.0) -> None:
        """
        Эмуляция continuous move через маленькие абсолютные шаги.
        x/y/zoom приходят как скорости в диапазоне [-1, 1].
        """
        x = _clamp(x, -1.0, 1.0)
        y = _clamp(y, -1.0, 1.0)
        zoom = _clamp(zoom, -1.0, 1.0)

        if x != 0.0 or y != 0.0:
            current_az = self._last_azimut if self._last_azimut is not None else 0.0
            next_az = normalize_deg(current_az + x * self._continuous_step_deg)
            next_el = _clamp(
                self._last_elevation + y * self._continuous_step_deg,
                MIN_ELEVATION_DEG,
                MAX_ELEVATION_DEG,
            )
            self._move_absolute(next_az, next_el)

        if zoom != 0.0:
            self.set_zoom(zoom)

    def stop(self, pan_tilt: bool = True, zoom: bool = True) -> None:
        """
        В минимальной документации нет endpoint для stop.
        Оставляем метод идемпотентным, чтобы общий сервисный слой работал единообразно.
        """
        logger.info(
            "China stop requested: device_id=%s pan_tilt=%s zoom=%s; no-op by protocol",
            self.device_id,
            pan_tilt,
            zoom,
        )

    def set_zoom(self, delta: float) -> None:
        """
        Относительный zoom поверх absolute API.
        delta > 0 увеличивает текущий zoom factor, delta < 0 уменьшает, минимум — 1x.
        """
        delta = _clamp(delta, -1.0, 1.0)
        if delta == 0.0:
            return
        self._zoom_absolute(self._zoom_position + delta)

    def get_azimut(self) -> Optional[float]:
        """
        Минимальный HTTP API не даёт status endpoint, поэтому возвращаем последний
        успешно отправленный абсолютный азимут.
        """
        return self._last_azimut

    def close(self) -> None:
        self._client.close()
