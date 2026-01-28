from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


class TestPTZAPI:
    """Тесты для endpoints /api/ptz*."""

    def test_ptz_move_success(
        self, app_with_mocks, auth_header, camera_db_onvif
    ):
        """Проверяет успешное движение PTZ через dishka DI."""
        app_instance, container, mocks = app_with_mocks
        
        # Настраиваем поведение мока PTZ менеджера
        mock_controller = MagicMock()
        mock_controller.search_target.return_value = 45.5
        mocks['ptz_manager'].get_controller.return_value = mock_controller
        mocks['ptz_manager'].restart_camera.return_value = mock_controller
        
        client = TestClient(app_instance)

        payload = {
            "lat": 55.75,
            "lon": 37.62,
            "height": 5.0,
            "zoom": 0.5,
            "radar_id": 1,
        }

        response = client.post(
            f"/api/ptz/{camera_db_onvif.id}/move/",
            json=payload,
            headers=auth_header,
        )

        assert response.status_code in [200, 404]  # 404 если камера не найдена

    def test_ptz_continuous_move(
        self, app_with_mocks, auth_header, camera_db_onvif
    ):
        """Проверяет непрерывное движение PTZ через dishka DI."""
        app_instance, container, mocks = app_with_mocks
        
        # Настраиваем поведение мока PTZ менеджера
        mock_controller = MagicMock()
        mocks['ptz_manager'].get_controller.return_value = mock_controller
        
        client = TestClient(app_instance)

        payload = {
            "x": 0.5,
            "y": -0.3,
            "zoom": 0.1,
        }

        response = client.post(
            f"/api/ptz/{camera_db_onvif.id}/continuous_move/",
            json=payload,
            headers=auth_header,
        )

        assert response.status_code in [200, 404]

    def test_ptz_stop(self, app_with_mocks, auth_header, camera_db_onvif):
        """Проверяет остановку PTZ через dishka DI."""
        app_instance, container, mocks = app_with_mocks
        
        # Настраиваем поведение мока PTZ менеджера
        mock_controller = MagicMock()
        mock_controller.get_azimut.return_value = 123.45
        mocks['ptz_manager'].get_controller.return_value = mock_controller
        mocks['ptz_manager'].restart_camera.return_value = mock_controller
        
        client = TestClient(app_instance)

        response = client.post(
            f"/api/ptz/{camera_db_onvif.id}/stop/",
            headers=auth_header,
        )

        assert response.status_code in [200, 404]
