from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class GatewayCameraResponse(BaseModel):
    """
    DTO ответа API gateway по камере.

    Ожидаем плоскую схему (host/username/password/rtsp_url/geo), которую gateway отдаёт.
    """

    id: int
    name: Optional[str] = None

    host: str
    username: str
    password: str
    port: int = 554

    rtsp_url: str
    rtsp_url_ik: str

    lat: float
    lon: float
    height: float
    rate: float = 0.0
    ptz_type: str = "onvif"

    model_config = ConfigDict(extra="ignore")

