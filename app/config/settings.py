from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DetectorMode(str, Enum):
    """Режим детектора: оптический или тепловизионный."""

    OPTICAL = "optical"
    THERMAL = "thermal"


# ---------- Модель камеры ----------


class CameraConfig(BaseModel):
    id: int = Field(..., description="ID камеры (число)")
    name: str = Field(None, description="Имя камеры")
    host: str = Field(..., description="IP/домен камеры")
    user: str = Field(..., description="Логин ONVIF/RTSP")
    password: str = Field(..., description="Пароль ONVIF/RTSP")
    port: int = Field(554, description="Порт ONVIF/RTSP, по умолчанию 554")
    rtsp_url: str = Field(..., description="Полный RTSP URL")
    rtsp_url_ik: str = Field(..., description="Полный RTSP URL")

    lat: float = Field(..., description="Широта камеры")
    lon: float = Field(..., description="Долгота камеры")
    height: float = Field(..., ge=0, description="Высота камеры над землёй (м)")
    rate: float = Field(
        0.0,
        description="Смещение камеры относительно севера (°). Компенсация ориентации корпуса.",
    )
    zoom_speed: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description="Множитель скорости зума (0.0–1.0). 1.0 = максимальная скорость камеры.",
    )
    ptz_type: str = Field(
        "onvif",
        description="Тип PTZ контроллера: 'onvif' или 'tms20'",
    )

    def is_tms20(self) -> bool:
        return self.ptz_type.lower() == "tms20"

    @classmethod
    def from_db_model(cls, camera) -> CameraConfig:
        return cls(
            id=camera.id,
            name=camera.name,
            host=camera.connection.host,
            user=camera.connection.username,
            password=camera.connection.password,
            port=camera.connection.port,
            rtsp_url=camera.connection.rtsp_url,
            rtsp_url_ik=camera.connection.rtsp_url_ik,
            lat=camera.location.lat,
            lon=camera.location.lon,
            height=camera.location.height,
            rate=camera.location.rate,
            ptz_type=camera.ptz.ptz_type.type,
        )


# ---------- Основной конфиг приложения ----------


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",  # позволим добавлять новые атрибуты (camera1_host и т.п.)
    )

    # API
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    app_token: str = Field(..., description="Bearer-токен API")

    # External services
    camera_api_base_url: str = Field(
        default="http://localhost:8080",
        alias="CAMERA_API_BASE_URL",
        description="Base URL API gateway для получения данных камер",
    )
    camera_api_token: Optional[str] = Field(
        default=None,
        alias="CAMERA_API_TOKEN",
        description="Bearer-токен для API gateway (если требуется)",
    )

    # Список камер из .env: CAMERAS=1,2
    cameras_raw: str = Field("", alias="CAMERAS")

    # DETECTION
    detector_weights_optical: str = Field(
        default="optical.pt",
        description="Файл весов YOLO для оптического режима (относительно корня проекта)",
    )
    detector_weights_thermal: str = Field(
        default="thermal.pt",
        description="Файл весов YOLO для тепловизионного режима (относительно корня проекта)",
    )
    detector_default_mode: DetectorMode = Field(
        default=DetectorMode.OPTICAL,
        description="Режим детектора по умолчанию при старте",
    )
    detector_conf: float = Field(0.3, ge=0, le=1)
    detector_device: Optional[str] = None  # cpu / cuda / xpu — если нужно форсить
    # STREAMING

    HOST_RECV_SERVER: str = "127.0.0.1"
    PORT_RECV_SERVER: int = 51242

    # RADAR HEIGHTS
    heights: list[float] = Field(
        default=[0.0],
        description="Список высот радаров: индекс = radar_id - 1",
    )


@lru_cache
def get_config() -> AppConfig:
    """
    Возвращает конфигурацию приложения.
    Камеры НЕ загружаются при старте — данные берутся из БД при каждом запросе.
    """
    return AppConfig()


config = get_config()
