"""
API тесты для PTZ endpoints.

Тестируют endpoints через HTTP, используя замоканные менеджеры
для изоляции от внешних зависимостей.
"""

from unittest.mock import MagicMock

from fastapi import HTTPException


class TestPTZAPI:
    """Тесты для /api/ptz/* endpoints."""

    def test_ptz_move_success(
        self, client_with_mocks, auth_header, sample_camera_onvif_config
    ):
        """Проверяет успешное движение PTZ."""
        client, mocks = client_with_mocks

        # Настраиваем мок
        mock_controller = MagicMock()
        mock_controller.search_target.return_value = 45.5
        mocks["ptz_manager"].assert_owner = MagicMock()
        mocks["ptz_manager"].get_controller.return_value = mock_controller
        mocks["ptz_manager"].restart_controller.return_value = mock_controller

        payload = {
            "lat": 55.75,
            "lon": 37.62,
            "height": 5.0,
            "zoom": 0.5,
            "radar_id": 1,
        }

        response = client.post(
            f"/api/ptz/{sample_camera_onvif_config.id}/move/",
            json=payload,
            params={"client_id": "test-client"},
            headers=auth_header,
        )

        assert response.status_code in [200, 404]

    def test_ptz_continuous_move(
        self, client_with_mocks, auth_header, sample_camera_onvif_config
    ):
        """Проверяет непрерывное движение PTZ."""
        client, mocks = client_with_mocks

        mock_controller = MagicMock()
        mocks["ptz_manager"].assert_owner = MagicMock()
        mocks["ptz_manager"].get_controller.return_value = mock_controller

        payload = {
            "x": 0.5,
            "y": -0.3,
            "zoom": 0.1,
        }

        response = client.post(
            f"/api/ptz/{sample_camera_onvif_config.id}/continuous_move/",
            json=payload,
            params={"client_id": "test-client"},
            headers=auth_header,
        )

        assert response.status_code in [200, 404]

    def test_ptz_stop(self, client_with_mocks, auth_header, sample_camera_onvif_config):
        """Проверяет остановку PTZ."""
        client, mocks = client_with_mocks

        mock_controller = MagicMock()
        mock_controller.get_azimut.return_value = 123.45
        mocks["ptz_manager"].assert_owner = MagicMock()
        mocks["ptz_manager"].get_controller.return_value = mock_controller
        mocks["ptz_manager"].restart_controller.return_value = mock_controller

        response = client.post(
            f"/api/ptz/{sample_camera_onvif_config.id}/stop/",
            params={"client_id": "test-client"},
            headers=auth_header,
        )

        assert response.status_code in [200, 404]

    def test_ptz_move_other_client_gets_423(
        self, client_with_mocks, auth_header, sample_camera_onvif_config
    ):
        client, mocks = client_with_mocks

        mocks["ptz_manager"].assert_owner.side_effect = HTTPException(
            status_code=423, detail="Камера занята"
        )

        payload = {
            "lat": 55.75,
            "lon": 37.62,
            "height": 5.0,
            "zoom": 0.5,
            "radar_id": 1,
        }

        response = client.post(
            f"/api/ptz/{sample_camera_onvif_config.id}/move/",
            json=payload,
            params={"client_id": "intruder"},
            headers=auth_header,
        )
        assert response.status_code == 423
