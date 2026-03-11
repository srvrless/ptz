"""
Integration тесты для CameraService.

После перехода на API gateway сервис не читает конфиг из БД напрямую,
поэтому здесь проверяем контракт: сервис берёт CameraConfig через gateway.
"""

from unittest.mock import MagicMock

import pytest

from app.config.settings import AppConfig, CameraConfig
from app.core.camera.manager import CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.exceptions import CameraNotFoundError
from app.services.camera_gateway_client import CameraGatewayClient
from app.services.camera_service import CameraService


class TestCameraService:
    def test_get_camera_config_success(self, sample_camera_onvif_config):
        gateway = MagicMock(spec=CameraGatewayClient)
        gateway.get_camera_config_by_id.return_value = sample_camera_onvif_config

        service = CameraService(
            camera_manager=MagicMock(spec=CameraManager),
            auto_ptz_manager=MagicMock(spec=AutoPTZManager),
            detector_manager=MagicMock(spec=DetectorManager),
            config=MagicMock(spec=AppConfig),
            camera_gateway=gateway,
        )

        cfg = service.get_camera_config(MagicMock(), camera_id=sample_camera_onvif_config.id)
        assert isinstance(cfg, CameraConfig)
        assert cfg.id == sample_camera_onvif_config.id

    def test_get_camera_config_not_found_raises(self):
        gateway = MagicMock(spec=CameraGatewayClient)
        gateway.get_camera_config_by_id.return_value = None

        service = CameraService(
            camera_manager=MagicMock(spec=CameraManager),
            auto_ptz_manager=MagicMock(spec=AutoPTZManager),
            detector_manager=MagicMock(spec=DetectorManager),
            config=MagicMock(spec=AppConfig),
            camera_gateway=gateway,
        )

        with pytest.raises(CameraNotFoundError):
            service.get_camera_config(MagicMock(), camera_id=999)
