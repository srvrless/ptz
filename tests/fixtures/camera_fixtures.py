import pytest
from app.config.settings import CameraConfig


@pytest.fixture
def sample_camera_onvif_config():
    """Конфиг ONVIF камеры."""
    return CameraConfig(
        id=1,
        name="Test Camera ONVIF",
        host="192.168.1.100",
        user="admin",
        password="password123",
        port=8080,
        rtsp_url="rtsp://192.168.1.100:554/stream1",
        lat=55.751244,
        lon=37.618423,
        height=15.5,
        rate=0.0,
        ptz_type="onvif",
    )


@pytest.fixture
def sample_camera_tms20_config():
    """Конфиг TMS-20 камеры."""
    return CameraConfig(
        id=2,
        name="Test Camera TMS-20",
        host="192.168.1.101",
        user="admin",
        password="password123",
        port=1470,
        rtsp_url="rtsp://192.168.1.101:554/stream1",
        lat=55.755814,
        lon=37.617635,
        height=12.0,
        rate=10.0,
        ptz_type="tms20",
    )