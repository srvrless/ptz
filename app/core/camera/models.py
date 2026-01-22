# app/core/camera/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraConnection:
    """
    Низкоуровневая информация для подключения к камере.
    Здесь только то, что нужно именно для VideoCapture/стрима.
    """

    url: str
