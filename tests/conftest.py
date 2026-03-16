from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Добавляем корень проекта в sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Настройки окружения для тестов (ДО импортов app.*)
os.environ["APP_DEBUG"] = "true"
os.environ["APP_PORT"] = "8000"
os.environ["APP_HOST"] = "0.0.0.0"
os.environ["APP_TOKEN"] = "test-token-123"
os.environ["DETECTOR_CONF"] = "0.3"
os.environ["DETECTOR_DEVICE"] = "cpu"
os.environ["HOST_RECV_SERVER"] = "127.0.0.1"
os.environ["PORT_RECV_SERVER"] = "51242"


@pytest.fixture(scope="session")
def camera_configs(sample_camera_onvif_config, sample_camera_tms20_config):
    return {
        sample_camera_onvif_config.id: sample_camera_onvif_config,
        sample_camera_tms20_config.id: sample_camera_tms20_config,
    }


@pytest.fixture(scope="session")
def app(camera_configs):
    """
    FastAPI приложение для тестов.

    В проекте нет БД/UoW: конфиги камер приходят через gateway.
    Поэтому в тестах поднимаем приложение с мок-менеджерами + мок-gateway.
    """
    from tests.dishka_overrides import create_test_app_with_mocks

    app_instance, container = create_test_app_with_mocks(camera_configs=camera_configs)
    try:
        yield app_instance
    finally:
        container.close()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def client_with_mocks(camera_configs):
    """
    HTTP клиент с замоканными менеджерами для API тестов.

    Возвращает: (client, mocks_dict)
    где mocks_dict содержит: {'camera_manager', 'ptz_manager', 'auto_ptz_manager', 'detector_manager'}.
    """
    from app.core.camera.manager import CameraManager
    from app.core.detection.yolo_detector import DetectorManager
    from app.core.ptz.manager import PTZCameraManager
    from app.core.tracking.auto_ptz_manager import AutoPTZManager
    from tests.dishka_overrides import create_test_app_with_mocks

    camera_manager_mock = MagicMock(spec=CameraManager)
    ptz_manager_mock = MagicMock(spec=PTZCameraManager)
    auto_ptz_manager_mock = MagicMock(spec=AutoPTZManager)
    detector_manager_mock = MagicMock(spec=DetectorManager)

    app_instance, container = create_test_app_with_mocks(
        camera_configs=camera_configs,
        camera_manager_mock=camera_manager_mock,
        ptz_manager_mock=ptz_manager_mock,
        auto_ptz_manager_mock=auto_ptz_manager_mock,
        detector_manager_mock=detector_manager_mock,
    )

    mocks = {
        "camera_manager": camera_manager_mock,
        "ptz_manager": ptz_manager_mock,
        "auto_ptz_manager": auto_ptz_manager_mock,
        "detector_manager": detector_manager_mock,
    }

    try:
        yield TestClient(app_instance), mocks
    finally:
        container.close()


@pytest.fixture
def auth_header():
    """Bearer токен для авторизации."""
    token = os.getenv("APP_TOKEN", "test-token-123")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def invalid_auth_header():
    """Невалидный токен."""
    return {"Authorization": "Bearer invalid-token"}


@pytest.fixture(scope="session")
def sample_camera_onvif_config():
    """Конфиг ONVIF камеры."""
    from app.config.settings import CameraConfig

    return CameraConfig(
        id=1,
        name="Test Camera ONVIF",
        host="192.168.1.100",
        user="admin",
        password="password123",
        port=8080,
        rtsp_url="rtsp://192.168.1.100:554/stream1",
        rtsp_url_ik="rtsp://192.168.1.101:554/stream1",
        lat=55.751244,
        lon=37.618423,
        height=15.5,
        rate=0.0,
        ptz_type="onvif",
    )


@pytest.fixture(scope="session")
def sample_camera_tms20_config():
    """Конфиг TMS-20 камеры."""
    from app.config.settings import CameraConfig

    return CameraConfig(
        id=2,
        name="Test Camera TMS-20",
        host="192.168.1.101",
        user="admin",
        password="password123",
        port=1470,
        rtsp_url="rtsp://192.168.1.101:554/stream1",
        rtsp_url_ik="rtsp://192.168.1.101:554/stream1",
        lat=55.755814,
        lon=37.617635,
        height=12.0,
        rate=10.0,
        ptz_type="tms20",
    )
