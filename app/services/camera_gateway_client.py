from __future__ import annotations

from typing import Optional

import httpx

from app.config.settings import CameraConfig
from app.schemas.camera_gateway import GatewayCameraResponse


class CameraGatewayClient:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    @staticmethod
    def _to_camera_config(camera: GatewayCameraResponse) -> CameraConfig:
        return CameraConfig(
            id=camera.id,
            name=camera.name,
            host=camera.host,
            user=camera.username,
            password=camera.password,
            port=camera.port,
            rtsp_url=camera.rtsp_url,
            rtsp_url_ik=camera.rtsp_url_ik,
            lat=camera.lat,
            lon=camera.lon,
            height=camera.height,
            rate=camera.rate,
            ptz_type=camera.ptz_type,
        )
    def get_camera_config_by_id(self, camera_id: int) -> Optional[CameraConfig]:
        resp = self._client.get(f"/v1/cameras/camera/{camera_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        camera = GatewayCameraResponse.model_validate(resp.json())
        return self._to_camera_config(camera)

    def get_nearest_camera_config(
        self,
        *,
        lat: float,
        lon: float,
        excluded_cameras_id: list[int] | None
    ) -> Optional[CameraConfig]:
        payload = {
            "lat": lat,
            "lon": lon,
            "excluded_cameras_id": excluded_cameras_id,
        }

        # gateway endpoint в примере — Post c JSON body (нестандартно, но поддерживаем)
        resp = self._client.request(
            "POST", f"/v1/cameras/nearest_camera/", json=payload
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        camera = GatewayCameraResponse.model_validate(resp.json())
        return self._to_camera_config(camera)

