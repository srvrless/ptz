import pytest


class TestCamerasAPI:
    """Тесты для endpoints /api/cameras*."""
    
    def test_get_cameras_success(self, client, auth_header, camera_db_onvif, camera_db_tms20):
        """Проверяет успешное получение списка камер."""
        response = client.get("/api/cameras", headers=auth_header)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_camera_by_id(self, client, auth_header, camera_db_onvif):
        """Проверяет получение камеры по ID."""
        camera_id = camera_db_onvif.id
        response = client.get(
            f"/api/camera/{camera_id}",
            headers=auth_header,
        )
        
        # Камера должна быть найдена и активна
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "PERGAM1"
        assert data["id"] == camera_id