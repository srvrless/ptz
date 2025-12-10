from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------- Модель камеры ----------

class CameraConfig(BaseModel):
    id: str = Field(..., description="ID камеры (ключ)")
    host: str = Field(..., description="IP/домен камеры")
    user: str = Field(..., description="Логин ONVIF/RTSP")
    password: str = Field(..., description="Пароль ONVIF/RTSP")
    port: int = Field(554, description="Порт ONVIF/RTSP, по умолчанию 554")
    rtsp_url: str = Field(..., description="Полный RTSP URL")

    lat: float = Field(..., description="Широта камеры")
    lon: float = Field(..., description="Долгота камеры")
    height: float = Field(..., ge=0, description="Высота камеры над землёй (м)")
    rate: float = Field(
        0.0,
        description="Смещение камеры относительно севера (°). Компенсация ориентации корпуса.",
    )

    ptz_type: str = Field(
        "onvif",
        description="Тип PTZ контроллера: 'onvif' или 'tms20'",
    )

    def is_tms20(self) -> bool:
        return self.ptz_type.lower() == "tms20"


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

    # Список камер из .env: CAMERAS=1,2
    cameras_raw: str = Field("", alias="CAMERAS")

    # DETECTION
    detector_weights: Optional[str] = Field(
        default="best.pt",
        description="Файл весов YOLO (относительно корня проекта)",
    )
    detector_conf: float = Field(0.3, ge=0, le=1)
    detector_device: Optional[str] = None  # cpu / cuda / xpu — если нужно форсить
    # STREAMING
    
    HOST_RECV_SERVER: str
    PORT_RECV_SERVER: int

    # RADAR HEIGHTS
    heights: list[float] = Field(
        default=[0.0],
        description="Список высот радаров: индекс = radar_id - 1",
    )


def _load_cameras_from_settings(cfg: AppConfig) -> Dict[str, CameraConfig]:
    """
    Собираем камеры не из os.environ, а из самого AppConfig,
    куда pydantic-settings уже прочитал .env.
    """
    cameras: Dict[str, CameraConfig] = {}

    cam_ids_raw = cfg.cameras_raw
    if not cam_ids_raw:
        return cameras

    for cam_num in cam_ids_raw.split(","):
        cam_num = cam_num.strip()
        if not cam_num:
            continue

        cam_id = f"camera{cam_num}"

        try:
            host = getattr(cfg, f"camera{cam_num}_host")
            user = getattr(cfg, f"camera{cam_num}_user")
            password = getattr(cfg, f"camera{cam_num}_password")
            port_raw = getattr(cfg, f"camera{cam_num}_port", 554)
            rtsp_url = getattr(cfg, f"camera{cam_num}_rtsp_url")

            lat_raw = getattr(cfg, f"camera{cam_num}_lat")
            lon_raw = getattr(cfg, f"camera{cam_num}_lon")
            height_raw = getattr(cfg, f"camera{cam_num}_height")
            rate_raw = getattr(cfg, f"camera{cam_num}_rate", 0)
            ptz_type = getattr(cfg, f"camera{cam_num}_ptz_type", "onvif")

            cam_cfg = CameraConfig(
                id=cam_id,
                host=str(host),
                user=str(user),
                password=str(password),
                port=int(port_raw),
                rtsp_url=str(rtsp_url),
                lat=float(lat_raw),
                lon=float(lon_raw),
                height=float(height_raw),
                rate=float(rate_raw),
                ptz_type=str(ptz_type),
            )
        except (AttributeError, TypeError, ValueError, ValidationError) as exc:
            raise ValueError(f"Invalid configuration for {cam_id}: {exc}")

        cameras[cam_id] = cam_cfg

    return cameras


@lru_cache
def get_config() -> AppConfig:
    cfg = AppConfig()
    cfg.cameras: Dict[str, CameraConfig] = _load_cameras_from_settings(cfg)
    # можно оставить отладочный вывод
    print("Loaded config:", cfg.model_dump(exclude={"app_token"}))
    return cfg


config = get_config()
