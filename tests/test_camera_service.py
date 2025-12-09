# tests/test_camera_service.py
import numpy as np

from app.services import camera_service
from app.core.camera import manager as cam_manager_module


class DummyCamera:
    def __init__(self):
        self.counter = 0

    def get_frame(self):
        self.counter += 1
        return np.zeros((100, 100, 3), dtype=np.uint8)


def test_camera_service_list_cameras():
    cams = camera_service.list_cameras()
    assert "camera1" in cams
    assert "camera2" in cams
    assert cams["camera1"]["host"] == "192.168.0.10"


def test_camera_service_mjpeg_stream(monkeypatch):
    dummy_camera = DummyCamera()

    def fake_get_or_create(camera_id, conn):
        return dummy_camera

    monkeypatch.setattr(
        cam_manager_module.camera_manager,
        "get_or_create",
        fake_get_or_create,
    )

    gen = camera_service.get_mjpeg_stream("camera1", enable_detection=False)

    # берём несколько кусков из генератора
    for _ in range(3):
        chunk = next(gen)
        assert isinstance(chunk, (bytes, bytearray))

    assert dummy_camera.counter >= 1
