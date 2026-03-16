"""
Тесты для streaming endpoints с использованием dishka.

После интеграции dishka, зависимости переопределяются через
контейнер вместо глобальных патчей.
"""


class TestStreamsAPI:
    """Тесты для endpoints /api/camera/select, /api/camera/selected."""

    def test_select_camera_success(
        self,
        client_with_mocks,
        sample_camera_onvif_config,
    ):
        """
        Проверяет выбор камеры из БД.

        Использует client из conftest.py, который уже настроен
        с dishka и тестовой БД.
        """
        client, _mocks = client_with_mocks

        response = client.post(
            f"/api/camera/select/{sample_camera_onvif_config.id}",
            params={"client_id": "test-client"},
            headers={"x-client-id": "test-client"},
        )

        # Может быть 200 (успех)
        assert response.status_code == 200

        if response.status_code == 200:
            data = response.json()
            assert data["selected_camera_id"] == sample_camera_onvif_config.id

    def test_stop_selected_camera(self, client):
        """Проверяет остановку выбранной камеры."""
        response = client.post(
            "/api/camera/stop",
            params={"client_id": "test-client"},
            headers={"x-client-id": "test-client"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["stopped"] is True

    def test_two_clients_can_select_different_cameras(
        self,
        client_with_mocks,
        sample_camera_onvif_config,
        sample_camera_tms20_config,
    ):
        client, _mocks = client_with_mocks

        r1 = client.post(
            f"/api/camera/select/{sample_camera_onvif_config.id}",
            params={"client_id": "c1"},
            headers={"x-client-id": "c1"},
        )
        r2 = client.post(
            f"/api/camera/select/{sample_camera_tms20_config.id}",
            params={"client_id": "c2"},
            headers={"x-client-id": "c2"},
        )

        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_busy_camera_second_client_gets_423(
        self,
        client_with_mocks,
        sample_camera_onvif_config,
    ):
        client, _mocks = client_with_mocks

        r1 = client.post(
            f"/api/camera/select/{sample_camera_onvif_config.id}",
            params={"client_id": "c1"},
            headers={"x-client-id": "c1"},
        )
        assert r1.status_code == 200

        r2 = client.post(
            f"/api/camera/select/{sample_camera_onvif_config.id}",
            params={"client_id": "c2"},
            headers={"x-client-id": "c2"},
        )
        assert r2.status_code == 423
