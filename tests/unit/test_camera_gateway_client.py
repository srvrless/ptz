from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.services.camera_gateway_client import CameraGatewayClient


def _gateway_camera_payload(*, camera_id: int = 10) -> dict[str, Any]:
    return {
        "id": camera_id,
        "name": f"Cam {camera_id}",
        "host": "10.0.0.10",
        "username": "admin",
        "password": "pass",
        "port": 554,
        "rtsp_url": "rtsp://10.0.0.10/optical",
        "rtsp_url_ik": "rtsp://10.0.0.10/thermal",
        "lat": 55.75,
        "lon": 37.62,
        "height": 12.5,
        "rate": 0.0,
        "ptz_type": "onvif",
    }


def _httpx_response(
    *,
    status_code: int,
    json_data: Any | None = None,
    method: str = "GET",
    url: str = "http://test",
) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status_code=status_code, json=json_data, request=request)


@pytest.mark.unit
class TestCameraGatewayClientGetCameraConfigById:
    def test_returns_none_on_404(self) -> None:
        http_client = MagicMock()
        http_client.get.return_value = _httpx_response(status_code=404)
        client = CameraGatewayClient(http_client)

        assert client.get_camera_config_by_id(123) is None
        http_client.get.assert_called_once_with("/v1/cameras/camera/123")

    def test_maps_gateway_payload_to_camera_config(self) -> None:
        http_client = MagicMock()
        http_client.get.return_value = _httpx_response(
            status_code=200,
            json_data=_gateway_camera_payload(camera_id=7),
            url="http://test/v1/cameras/camera/7",
        )
        client = CameraGatewayClient(http_client)

        cfg = client.get_camera_config_by_id(7)
        assert cfg is not None
        assert cfg.id == 7
        assert cfg.host == "10.0.0.10"
        assert cfg.user == "admin"
        assert cfg.rtsp_url.endswith("/optical")


@pytest.mark.unit
class TestCameraGatewayClientPostNearestCameraConfig:
    def test_sends_post_with_json_body_and_returns_none_on_404(self) -> None:
        http_client = MagicMock()
        http_client.request.return_value = _httpx_response(
            status_code=404, method="POST"
        )
        client = CameraGatewayClient(http_client)

        cfg = client.get_nearest_camera_config(
            lat=55.0,
            lon=37.0,
        )
        assert cfg is None

        http_client.request.assert_called_once_with(
            "POST",
            "/v1/cameras/nearest_camera/",
            json={"lat": 55.0, "lon": 37.0},
        )

    def test_maps_gateway_payload_to_camera_config(self) -> None:
        http_client = MagicMock()
        http_client.request.return_value = _httpx_response(
            status_code=200,
            json_data=_gateway_camera_payload(camera_id=42),
            method="POST",
            url="http://test/v1/cameras/nearest_camera/",
        )
        client = CameraGatewayClient(http_client)

        cfg = client.get_nearest_camera_config(
            lat=55.75,
            lon=37.62,
        )
        assert cfg is not None
        assert cfg.id == 42
        assert cfg.ptz_type == "onvif"
