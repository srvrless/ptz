from unittest.mock import MagicMock, patch


class TestStreamsAPI:
    """Тесты для endpoints /api/camera/select, /api/camera/selected."""

    def test_select_camera_success(
        self,
        client,
        auth_header,
        camera_db_onvif,
        monkeypatch,
    ):
        """Проверяет выбор камеры из БД."""
        with patch("app.services.camera_service.camera_manager") as mock_manager:
            with patch("app.services.camera_service.run_detection_sender"):
                mock_camera = MagicMock()
                mock_manager.get_or_create.return_value = mock_camera

                # Мокируем конфиг, чтобы камера была найдена
                from app.config.settings import CameraConfig, AppConfig

                config_dict = {
                    camera_db_onvif.id: CameraConfig(
                        id=camera_db_onvif.id,
                        name=camera_db_onvif.name,
                        host=camera_db_onvif.connection.host,
                        user=camera_db_onvif.connection.username,
                        password=camera_db_onvif.connection.password,
                        port=camera_db_onvif.connection.port,
                        rtsp_url=camera_db_onvif.connection.rtsp_url,
                        lat=camera_db_onvif.location.lat,
                        lon=camera_db_onvif.location.lon,
                        height=camera_db_onvif.location.height,
                        rate=camera_db_onvif.location.rate,
                        ptz_type=camera_db_onvif.ptz_type,
                    )
                }

                # Patch get_config to return mocked config
                mock_config = MagicMock(spec=AppConfig)
                mock_config.cameras = config_dict
                monkeypatch.setattr(
                    "app.api.v1.dependencies.get_config",
                    lambda: mock_config,
                )

                response = client.post(
                    f"/api/camera/select/{camera_db_onvif.id}",
                    headers=auth_header,
                )

                assert response.status_code == 200
                data = response.json()
                assert data["selected_camera_id"] == camera_db_onvif.id

    def test_stop_selected_camera(self, client, auth_header):
        """Проверяет остановку выбранной камеры."""
        response = client.post(
            "/api/camera/stop",
            headers=auth_header,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["stopped"] is True
