# app/utils/geo.py
import math
from typing import Tuple

M_PER_DEG_LAT = 111_320.0  # метров на градус широты (приближение)


def normalize_deg(angle: float) -> float:
    """
    Нормализует угол в диапазон [0, 360).
    """
    return angle % 360.0


def normalize_relative(angle: float) -> float:
    """
    Нормализует угол в диапазон (-180, 180].
    Удобно для "поворотов" вправо/влево.
    """
    a = normalize_deg(angle)
    if a > 180.0:
        a -= 360.0
    return a


def haversine_distance_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    Приближённое расстояние по поверхности Земли в метрах.
    a, b: (lat, lon) в градусах.
    """
    lat1, lon1 = a
    lat2, lon2 = b

    r = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    sin_dphi = math.sin(dphi / 2.0)
    sin_dlambda = math.sin(dlambda / 2.0)

    h = sin_dphi**2 + math.cos(phi1) * math.cos(phi2) * sin_dlambda**2
    return 2 * r * math.asin(math.sqrt(h))


def azimuth_from_latlon(
    cam_latlon: Tuple[float, float],
    target_latlon: Tuple[float, float],
    cam_rate_deg: float = 0.0,
) -> float:
    """
    Азимут от камеры к цели в градусах относительно севера (0 = север, 90 = восток).
    cam_rate_deg — поправка ориентации камеры относительно севера (смещение башки).
    """
    lat1, lon1 = map(math.radians, cam_latlon)
    lat2, lon2 = map(math.radians, target_latlon)

    dlon = lon2 - lon1

    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        dlon
    )

    brng = math.degrees(math.atan2(x, y))  # в диапазоне (-180, 180]
    brng = normalize_deg(brng)  # -> [0, 360)

    # учитываем угол установки камеры (rate)
    return normalize_deg(brng + cam_rate_deg)


def elevation_from_latlon(
    cam_latlon: Tuple[float, float],
    cam_h: float,
    target_latlon: Tuple[float, float],
    target_h: float,
    radar_h: float,
) -> float:
    """
    Угол места (elevation) от камеры к цели в градусах.

    cam_h     — высота камеры над уровнем земли (м)
    target_h  — высота цели над уровнем земли (м)
    radar_h   — высота радара над землёй (если цель задаётся относительно радара)
    """
    horizontal_dist = haversine_distance_m(cam_latlon, target_latlon)

    # допустим, target_h дана относительно радара → переводим к "миру"
    effective_target_h = target_h + radar_h
    dz = effective_target_h - cam_h

    # atan2 автоматически возвращает нужный знак
    angle_rad = math.atan2(dz, horizontal_dist)
    return math.degrees(angle_rad)


def relative_camera_turn(
    cam_latlon: Tuple[float, float],
    target_latlon: Tuple[float, float],
    current_cam_azimuth: float,
    cam_rate_deg: float = 0.0,
) -> float:
    """
    Как на сколько ПОВЕРНУТЬ камеру (°), чтобы посмотреть на цель.
    Положительное — вправо (по часовой), отрицательное — влево.
    """
    target_az = azimuth_from_latlon(cam_latlon, target_latlon, cam_rate_deg)
    return normalize_relative(target_az - current_cam_azimuth)
