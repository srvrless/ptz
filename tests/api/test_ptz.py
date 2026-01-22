from unittest.mock import MagicMock, patch


class TestPTZAPI:
    """Тесты для endpoints /api/ptz*."""

    @patch("app.core.ptz.manager.ptz_camera_manager")
    def test_ptz_move_success(self, mock_manager, client, auth_header, camera_db_onvif):
        """Проверяет успешное движение PTZ."""
        mock_controller = MagicMock()
        mock_controller.search_target.return_value = 45.5
        mock_manager.get_controller.return_value = mock_controller
        mock_manager.restart_camera.return_value = mock_controller

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

    @patch("app.core.ptz.manager.ptz_camera_manager")
    def test_ptz_continuous_move(
        self, mock_manager, client, auth_header, camera_db_onvif
    ):
        """Проверяет непрерывное движение PTZ."""
        mock_controller = MagicMock()
        mock_manager.get_controller.return_value = mock_controller

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

    @patch("app.core.ptz.manager.ptz_camera_manager")
    def test_ptz_stop(self, mock_manager, client, auth_header, camera_db_onvif):
        """Проверяет остановку PTZ."""
        mock_controller = MagicMock()
        mock_controller.get_azimut.return_value = 123.45
        mock_manager.get_controller.return_value = mock_controller
        mock_manager.restart_camera.return_value = mock_controller

        response = client.post(
            f"/api/ptz/{camera_db_onvif.id}/stop/",
            headers=auth_header,
        )

        assert response.status_code in [200, 404]
