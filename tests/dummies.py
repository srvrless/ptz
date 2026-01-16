from typing import Optional
import numpy as np
from app.config.settings import config
from app.core.ptz.base import BasePTZController

class DummyCamera:
    def __init__(self):
        self.counter = 0

    def get_frame(self):
        self.counter += 1
        return np.zeros((100, 100, 3), dtype=np.uint8)
    

class DummyOnvif:
    controller_type = "onvif"

    def __init__(self, *args, **kwargs):
        self.cam_latlon = (config.cameras["camera1"].lat, config.cameras["camera1"].lon)


class DummyTMS20:
    controller_type = "tms20"

    def __init__(self, *args, **kwargs):
        self.cam_latlon = (config.cameras["camera2"].lat, config.cameras["camera2"].lon)

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