from __future__ import annotations

from dataclasses import is_dataclass, asdict
from typing import Any, Dict

from pydantic import BaseModel

from app.config.settings import CameraConfig


def serialize_camera_config(cfg: CameraConfig) -> Dict[str, Any]:
    """
    Приводит CameraConfig к словарю для ответа API.
    Поддерживает как Pydantic-модели, так и dataclass'ы.
    Пароль по умолчанию не отдаём наружу.
    """
    if isinstance(cfg, BaseModel):
        data = cfg.model_dump()
    elif is_dataclass(cfg):
        data = asdict(cfg)
    else:
        # на всякий случай, если когда-то будет обычный dict
        data = dict(cfg)

    # не светим пароль наружу
    data.pop("password", None)
    return data


def serialize_cameras(cameras: Dict[str, CameraConfig]) -> Dict[str, Dict[str, Any]]:
    return {camera_id: serialize_camera_config(cfg) for camera_id, cfg in cameras.items()}
