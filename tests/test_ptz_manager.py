# tests/test_ptz_manager.py
from app.core.ptz import manager as mgr_module
from app.config.settings import config


class DummyOnvif:
    def __init__(self, *args, **kwargs):
        self.cam_latlon = (config.cameras["camera1"].lat, config.cameras["camera1"].lon)


class DummyTMS20:
    def __init__(self, *args, **kwargs):
        self.cam_latlon = (config.cameras["camera2"].lat, config.cameras["camera2"].lon)


def test_ptz_manager_creates_correct_controller_types(monkeypatch):
    # подменяем реальные контроллеры на заглушки
    monkeypatch.setattr(mgr_module, "PTZController", DummyOnvif)
    monkeypatch.setattr(mgr_module, "Tms20PTZController", DummyTMS20)

    mgr = mgr_module.PTZCameraManager()

    ctrl1 = mgr.get_controller("camera1")
    ctrl2 = mgr.get_controller("camera2")

    assert isinstance(ctrl1, DummyOnvif)
    assert isinstance(ctrl2, DummyTMS20)

    assert ctrl1.cam_latlon == (config.cameras["camera1"].lat, config.cameras["camera1"].lon)
    assert ctrl2.cam_latlon == (config.cameras["camera2"].lat, config.cameras["camera2"].lon)
