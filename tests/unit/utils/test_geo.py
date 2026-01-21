import pytest
import math

from app.utils.geo import (
    normalize_deg,
    normalize_relative,
    haversine_distance_m,
    azimuth_from_latlon,
    elevation_from_latlon,
)


class TestGeoUtilities:
    """Тесты для geo-утилит."""
    
    def test_normalize_deg_zero(self):
        """Проверяет нормализацию 0°."""
        assert normalize_deg(0.0) == 0.0
    
    def test_normalize_deg_360(self):
        """Проверяет нормализацию 360°."""
        assert normalize_deg(360.0) == pytest.approx(0.0, abs=0.01)
    
    def test_normalize_deg_negative(self):
        """Проверяет нормализацию отрицательного угла."""
        assert normalize_deg(-90.0) == pytest.approx(270.0, abs=0.01)
    
    def test_normalize_relative_zero(self):
        """Проверяет нормализацию relative 0°."""
        assert normalize_relative(0.0) == 0.0
    
    def test_normalize_relative_180(self):
        """Проверяет нормализацию relative 180°."""
        assert normalize_relative(180.0) == 180.0
    
    def test_normalize_relative_270(self):
        """Проверяет нормализацию 270° в (-180, 180]."""
        result = normalize_relative(270.0)
        assert result == pytest.approx(-90.0, abs=0.01)
    
    def test_haversine_distance_moscow(self):
        """Проверяет расстояние между двумя точками в Москве."""
        a = (55.7558, 37.6173)
        b = (55.7505, 37.6141)
        
        dist = haversine_distance_m(a, b)
        assert 500 < dist < 700
    
    def test_azimuth_north(self):
        """Проверяет азимут на северное направление."""
        cam = (55.0, 37.0)
        target = (56.0, 37.0)
        
        az = azimuth_from_latlon(cam, target, cam_rate_deg=0.0)
        assert az == pytest.approx(0.0, abs=1.0)
    
    def test_azimuth_east(self):
        """Проверяет азимут на восточное направление."""
        cam = (55.0, 37.0)
        target = (55.0, 38.0)
        
        az = azimuth_from_latlon(cam, target, cam_rate_deg=0.0)
        assert az == pytest.approx(90.0, abs=1.0)
    
    def test_elevation_positive(self):
        """Проверяет положительный угол места."""
        el = elevation_from_latlon(
            cam_latlon=(55.0, 37.0),
            cam_h=10.0,
            target_latlon=(55.0, 37.0),
            target_h=5.0,
            radar_h=0.0,
        )
        assert el < 0
    
    def test_elevation_negative(self):
        """Проверяет отрицательный угол места."""
        el = elevation_from_latlon(
            cam_latlon=(55.0, 37.0),
            cam_h=0.0,
            target_latlon=(55.0, 37.0),
            target_h=20.0,
            radar_h=0.0,
        )
        assert el > 0