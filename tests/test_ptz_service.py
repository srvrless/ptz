# tests/test_ptz_service.py
from typing import Optional

from app.services import ptz_service, PTZService
from app.core.ptz.base import BasePTZController


class DummyPTZ(BasePTZController):
    def __init__(self):
        super().__init__(cam_lat=55.0, cam_lon=37.0, cam_h=10.0, cam_rate=0.0)
        self.last_goto = None
        self.last_continuous = None
        self.last_zoom_delta = None
        self.stopped = False

    def goto_angles(self, az_deg: float, el_deg: float, zoom: Optional[float]):
        self.last_goto = (az_deg, el_deg, zoom)

    def continuous_move(self, x: float, y: float, zoom: float = 0.0):
        self.last_continuous = (x, y, zoom)

    def stop(self, pan_tilt: bool = True, zoom: bool = True):
        self.stopped = True

    def set_zoom(self, delta: float):
        self.last_zoom_delta = delta

    def get_azimut(self) -> Optional[float]:
        return 123.45


def test_ptz_service_move_to_target(monkeypatch):
    dummy = DummyPTZ()

    def fake_get_controller(self: PTZService, camera_id: str):
        return dummy

    monkeypatch.setattr(PTZService, "_get_controller", fake_get_controller)

    result = ptz_service.move_to_target(
        camera_id="camera1",
        lat=55.0,
        lon=37.0,
        height=5.0,
        zoom=0.5,
        radar_id=1,
    )

    assert result["status"] == "ok"
    assert "azimut" in result
    assert dummy.last_goto is not None


def test_ptz_service_continuous_move(monkeypatch):
    dummy = DummyPTZ()

    def fake_get_controller(self: PTZService, camera_id: str):
        return dummy

    monkeypatch.setattr(PTZService, "_get_controller", fake_get_controller)

    ptz_service.continuous_move("camera1", x=0.5, y=-0.5, zoom=0.1)
    assert dummy.last_continuous == (0.5, -0.5, 0.1)


def test_ptz_service_stop(monkeypatch):
    dummy = DummyPTZ()

    def fake_get_controller(self: PTZService, camera_id: str):
        return dummy

    monkeypatch.setattr(PTZService, "_get_controller", fake_get_controller)

    result = ptz_service.stop("camera1")
    assert result["status"] == "ok"
    assert result["azimut"] == 123.45
    assert dummy.stopped is True


def test_ptz_service_set_zoom(monkeypatch):
    dummy = DummyPTZ()

    def fake_get_controller(self: PTZService, camera_id: str):
        return dummy

    monkeypatch.setattr(PTZService, "_get_controller", fake_get_controller)

    ptz_service.set_zoom("camera1", zoom_delta=0.3)
    assert dummy.last_zoom_delta == 0.3
