from unittest.mock import MagicMock, patch

import pytest

from app.core.ptz.controller import PTZController


class TestPTZController:
    """Тесты для PTZController (ONVIF)."""

    @patch("app.core.ptz.controller.ONVIFCamera")
    def test_ptz_controller_initialization(self, mock_onvif):
        """Проверяет инициализацию PTZ контроллера."""
        mock_camera = MagicMock()
        mock_onvif.return_value = mock_camera

        mock_media = MagicMock()
        mock_ptz = MagicMock()
        mock_profile = MagicMock()
        mock_profile.token = "test_token"
        mock_status = MagicMock()

        mock_camera.create_media_service.return_value = mock_media
        mock_camera.create_ptz_service.return_value = mock_ptz
        mock_media.GetProfiles.return_value = [mock_profile]
        mock_ptz.GetStatus.return_value = mock_status

        controller = PTZController(
            host="192.168.1.100",
            user="admin",
            password="password",
            port=8080,
            cam_rate=0.0,
            cam_lat=55.751244,
            cam_lon=37.618423,
            cam_h=15.5,
        )

        assert controller.camera is not None
        assert controller.host == "192.168.1.100"

    def test_normalize_to_onvif_pan(self):
        """Проверяет нормализацию азимута в ONVIF pan."""
        with patch("app.core.ptz.controller.ONVIFCamera"):
            controller = PTZController(
                host="192.168.1.100",
                user="admin",
                password="password",
                port=8080,
                cam_rate=0.0,
                cam_lat=55.0,
                cam_lon=37.0,
                cam_h=10.0,
            )

            assert controller._normalize_to_onvif_pan(0.0) == -1.0
            assert controller._normalize_to_onvif_pan(180.0) == pytest.approx(
                0.0, abs=0.01
            )

    def test_normalize_to_onvif_tilt(self):
        """Проверяет нормализацию угла места в ONVIF tilt."""
        with patch("app.core.ptz.controller.ONVIFCamera"):
            controller = PTZController(
                host="192.168.1.100",
                user="admin",
                password="password",
                port=8080,
                cam_rate=0.0,
                cam_lat=55.0,
                cam_lon=37.0,
                cam_h=10.0,
            )

            assert controller._normalize_to_onvif_tilt(0.0) == 0.0
            assert controller._normalize_to_onvif_tilt(45.0) == 1.0
            assert controller._normalize_to_onvif_tilt(-45.0) == -1.0
            assert controller._normalize_to_onvif_tilt(90.0) == 1.0
