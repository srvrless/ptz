from unittest.mock import MagicMock, patch

from app.config.settings import CameraConfig
from app.core.ptz.china_controller import (
    ChinaPTZController,
    _base_url_from_host,
)
from app.core.ptz.factory import PTZControllerFactory


def _mock_response(payload: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload or {"code": 0, "status": "Success", "id": 1}
    return response


class TestChinaPTZController:
    def test_base_url_from_plain_host(self):
        assert _base_url_from_host("127.0.0.1", 8080) == "http://127.0.0.1:8080/api/"

    def test_base_url_from_full_api_url(self):
        assert (
            _base_url_from_host("http://127.0.0.1:18080/api", 8080)
            == "http://127.0.0.1:18080/api/"
        )

    @patch("app.core.ptz.china_controller.httpx.Client")
    def test_goto_angles_posts_absolute_move_and_zoom(self, mock_client_cls):
        client = MagicMock()
        client.post.return_value = _mock_response()
        mock_client_cls.return_value = client

        controller = ChinaPTZController(
            host="127.0.0.1",
            port=8080,
            device_id=1,
            user_id=1000,
            cam_lat=55.0,
            cam_lon=37.0,
            cam_h=10.0,
            cam_rate=0.0,
        )

        controller.goto_angles(az_deg=370.0, el_deg=-10.0, zoom=2.0)

        assert client.post.call_count == 2
        client.post.assert_any_call(
            "ptz/move/absolute",
            json={"id": 1, "user_id": 1000, "pan": 10.0, "tilt": 80.0, "speed": 30},
        )
        client.post.assert_any_call(
            "ptz/zoom/absolute",
            json={"id": 1, "user_id": 1000, "position": 2.0, "speed": 30},
        )
        assert controller.get_azimut() == 10.0

    @patch("app.core.ptz.china_controller.httpx.Client")
    def test_from_config_uses_default_http_port_for_rtsp_default(self, mock_client_cls):
        mock_client_cls.return_value = MagicMock()
        config = CameraConfig(
            id=7,
            name="China",
            host="localhost",
            user="admin",
            password="password",
            port=554,
            rtsp_url="rtsp://localhost/stream",
            rtsp_url_ik="rtsp://localhost/stream_ik",
            lat=55.0,
            lon=37.0,
            height=10.0,
            rate=0.0,
            ptz_type="china",
        )

        controller = ChinaPTZController.from_config(config)

        assert controller.base_url == "http://localhost:8080/api/"

    def test_factory_registration(self):
        assert "china" in PTZControllerFactory.get_available_types()
