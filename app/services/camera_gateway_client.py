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
            client_id=camera.client_id,
            is_busy=camera.is_busy,
        )

    def get_camera_config_by_id(self, camera_id: int) -> Optional[CameraConfig]:
        resp = self._client.get(f"/v1/cameras/camera/{camera_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        camera = GatewayCameraResponse.model_validate(resp.json())
        return self._to_camera_config(camera)

    def claim_camera(self, camera_id: int, client_id: str) -> CameraConfig:
        """
        Захватить камеру за client_id (атомарно на стороне gateway).
        Ожидаем, что gateway вернёт актуальную конфигурацию камеры.
        """
        resp = self._client.post(
            f"/v1/cameras/{camera_id}/claim",
            json={"client_id": client_id},
        )
        resp.raise_for_status()
        camera = GatewayCameraResponse.model_validate(resp.json())
        return self._to_camera_config(camera)

    def release_camera(self, camera_id: int, client_id: str) -> None:
        """Освободить камеру (только владелец может release)."""
        resp = self._client.post(
            f"/v1/cameras/{camera_id}/release",
            json={"client_id": client_id},
        )
        resp.raise_for_status()

    def get_nearest_camera_config(
        self,
        *,
        lat: float,
        lon: float,
    ) -> Optional[CameraConfig]:
        payload = {
            "lat": lat,
            "lon": lon,
        }

        # gateway endpoint в примере — Post c JSON body (нестандартно, но поддерживаем)
        resp = self._client.request("POST", "/v1/cameras/nearest_camera/", json=payload)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        camera = GatewayCameraResponse.model_validate(resp.json())
        return self._to_camera_config(camera)
