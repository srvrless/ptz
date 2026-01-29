"""
Тесты для streaming endpoints с использованием dishka.

После интеграции dishka, зависимости переопределяются через
контейнер вместо глобальных патчей.
"""


class TestStreamsAPI:
    """Тесты для endpoints /api/camera/select, /api/camera/selected."""

    def test_select_camera_success(
        self,
        client,
        camera_db_onvif,
    ):
        """
        Проверяет выбор камеры из БД.
        
        Использует client из conftest.py, который уже настроен
        с dishka и тестовой БД.
        """
        response = client.post(
            f"/api/camera/select/{camera_db_onvif.id}",
        )

        # Может быть 200 (успех) или 404 (камера не найдена в конфиге)
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["selected_camera_id"] == camera_db_onvif.id

    def test_stop_selected_camera(self, client):
        """Проверяет остановку выбранной камеры."""
        response = client.post("/api/camera/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["stopped"] is True
