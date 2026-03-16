from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class GatewayCameraResponse(BaseModel):
    """
    DTO ответа API gateway по камере.

    Ожидаем плоскую схему (host/username/password/rtsp_url/geo), которую gateway отдаёт.
    """

    id: int
    name: str

    host: str
    username: str
    password: str
    port: int
    rtsp_url: str
    rtsp_url_ik: str

    lat: float
    lon: float
    height: float
    rate: float
    ptz_type: str

    # Эти поля могут отсутствовать в старых версиях gateway.
    client_id: Optional[str] = None
    is_busy: bool = False

    model_config = ConfigDict(extra="ignore")
