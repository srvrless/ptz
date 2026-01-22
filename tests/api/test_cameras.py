class TestCamerasAPI:
    """Тесты для endpoints /api/cameras*."""

    def test_get_cameras_success(
        self, client, auth_header, camera_db_onvif, camera_db_tms20
    ):
        """Проверяет успешное получение списка камер."""
        response = client.get("/api/cameras", headers=auth_header)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
