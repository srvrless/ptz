# tests/test_settings.py
from app.config.settings import config, CameraConfig


def test_config_has_cameras():
    assert "camera1" in config.cameras
    assert "camera2" in config.cameras

    cam1 = config.cameras["camera1"]
    cam2 = config.cameras["camera2"]

    assert isinstance(cam1, CameraConfig)
    assert isinstance(cam2, CameraConfig)

    assert cam1.ptz_type.lower() == "onvif"
    assert cam2.ptz_type.lower() == "tms20"

    assert cam1.rtsp_url.startswith("rtsp://")
    assert cam2.rtsp_url.startswith("rtsp://")
