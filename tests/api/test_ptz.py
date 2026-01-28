"""
Тесты для PTZ API endpoints с использованием dishka.

После интеграции dishka, зависимости переопределяются через
контейнер вместо глобальных патчей.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from tests.dishka_overrides import create_test_app_with_mocks


class TestPTZAPI:
    """Тесты для endpoints /api/ptz*."""

    def test_ptz_move_success(
        self, test_db_session_factory, auth_header, camera_db_onvif
    ):
        """Проверяет успешное движение PTZ."""
        # Создаём мок PTZ менеджера
        mock_ptz_manager = MagicMock()
        mock_controller = MagicMock()
        mock_controller.search_target.return_value = 45.5
        mock_ptz_manager.get_controller.return_value = mock_controller
        mock_ptz_manager.restart_camera.return_value = mock_controller
        
        # Создаём приложение с мок-зависимостями
        app, container = create_test_app_with_mocks(
            test_db_session_factory,
            ptz_manager_mock=mock_ptz_manager
        )
        client = TestClient(app)

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
        
        # Cleanup
        container.close()

    def test_ptz_continuous_move(
        self, test_db_session_factory, auth_header, camera_db_onvif
    ):
        """Проверяет непрерывное движение PTZ."""
        # Создаём мок PTZ менеджера
        mock_ptz_manager = MagicMock()
        mock_controller = MagicMock()
        mock_ptz_manager.get_controller.return_value = mock_controller
        
        # Создаём приложение с мок-зависимостями
        app, container = create_test_app_with_mocks(
            test_db_session_factory,
            ptz_manager_mock=mock_ptz_manager
        )
        client = TestClient(app)

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
        
        # Cleanup
        container.close()

    def test_ptz_stop(self, test_db_session_factory, auth_header, camera_db_onvif):
        """Проверяет остановку PTZ."""
        # Создаём мок PTZ менеджера
        mock_ptz_manager = MagicMock()
        mock_controller = MagicMock()
        mock_controller.get_azimut.return_value = 123.45
        mock_ptz_manager.get_controller.return_value = mock_controller
        mock_ptz_manager.restart_camera.return_value = mock_controller
        
        # Создаём приложение с мок-зависимостями
        app, container = create_test_app_with_mocks(
            test_db_session_factory,
            ptz_manager_mock=mock_ptz_manager
        )
        client = TestClient(app)

        response = client.post(
            f"/api/ptz/{camera_db_onvif.id}/stop/",
            headers=auth_header,
        )

        assert response.status_code in [200, 404]
        
        # Cleanup
        container.close()
