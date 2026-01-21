import pytest
from app.config.settings import CameraConfig


class TestCameraConfig:
    """Тесты для CameraConfig."""
    
    def test_camera_config_creation(self, sample_camera_onvif_config):
        """Проверяет создание конфига камеры."""
        assert sample_camera_onvif_config.id == 1
        assert sample_camera_onvif_config.name == "Test Camera ONVIF"
        assert sample_camera_onvif_config.host == "192.168.1.100"
        assert sample_camera_onvif_config.ptz_type == "onvif"
    
    def test_is_tms20_true(self, sample_camera_tms20_config):
        """Проверяет is_tms20 для TMS-20."""
        assert sample_camera_tms20_config.is_tms20() is True
    
    def test_is_tms20_false(self, sample_camera_onvif_config):
        """Проверяет is_tms20 для ONVIF."""
        assert sample_camera_onvif_config.is_tms20() is False
    
    def test_camera_config_required_fields(self):
        """Проверяет, что обязательные поля валидируются."""
        with pytest.raises(Exception):
            CameraConfig(
                id=1,
                user="admin",
                password="pass",
                rtsp_url="rtsp://example",
                lat=55.0,
                lon=37.0,
                height=10.0,
            )
    
    def test_camera_config_height_non_negative(self):
        """Проверяет, что высота не может быть отрицательной."""
        with pytest.raises(Exception):
            CameraConfig(
                id=1,
                name="Test",
                host="192.168.1.1",
                user="admin",
                password="pass",
                rtsp_url="rtsp://example",
                lat=55.0,
                lon=37.0,
                height=-5.0,
            )