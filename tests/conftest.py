# tests/conftest.py
import os
import sys
from pathlib import Path

# --- добавить корень проекта в sys.path ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- окружение для тестов: ставим ДО импортов app.* ---
os.environ["APP_TOKEN"] = "test-token"

# две камеры: onvif и tms20
os.environ["CAMERAS"] = "1,2"

# CAMERA1 (onvif)
os.environ["CAMERA1_HOST"] = "192.168.0.10"
os.environ["CAMERA1_USER"] = "admin"
os.environ["CAMERA1_PASSWORD"] = "qwerty"
os.environ["CAMERA1_PORT"] = "8000"
os.environ["CAMERA1_RTSP_URL"] = "rtsp://example1"
os.environ["CAMERA1_LAT"] = "55.0"
os.environ["CAMERA1_LON"] = "37.0"
os.environ["CAMERA1_HEIGHT"] = "10"
os.environ["CAMERA1_RATE"] = "0"
os.environ["CAMERA1_PTZ_TYPE"] = "onvif"

# CAMERA2 (tms20)
os.environ["CAMERA2_HOST"] = "192.168.0.20"
os.environ["CAMERA2_USER"] = "admin"
os.environ["CAMERA2_PASSWORD"] = "qwerty"
os.environ["CAMERA2_PORT"] = "1470"
os.environ["CAMERA2_RTSP_URL"] = "rtsp://example2"
os.environ["CAMERA2_LAT"] = "55.1"
os.environ["CAMERA2_LON"] = "37.1"
os.environ["CAMERA2_HEIGHT"] = "12"
os.environ["CAMERA2_RATE"] = "10"
os.environ["CAMERA2_PTZ_TYPE"] = "tms20"

os.environ["HEIGHTS"] = "[5,10,15]"

# теперь можно импортировать всё остальное
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.streaming import mjpeg # noqa: E402
from app.core.camera import manager as cam_manager_module # noqa: E402
from tests.dummies import DummyCamera # noqa: E402
from tests.mocks import MockSocketConnection # noqa: E402
from tests.fakes import fake_imencode # noqa: E402


@pytest.fixture(scope="session")
def app_instance():
    return app


@pytest.fixture
def client(app_instance):
    return TestClient(app_instance)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}

@pytest.fixture
def dummy_camera():
    return DummyCamera()


@pytest.fixture
def mock_socket_connection(monkeypatch):
    conn = MockSocketConnection()

    monkeypatch.setattr(
        mjpeg,
        "_default_connection_factory",
        lambda: conn,
    )

    return conn


@pytest.fixture
def patched_camera_manager(monkeypatch, dummy_camera):
    monkeypatch.setattr(
        cam_manager_module.camera_manager,
        "get_or_create",
        lambda camera_id, conn: dummy_camera,
    )


@pytest.fixture
def patched_imencode(monkeypatch):
    monkeypatch.setattr("cv2.imencode", fake_imencode)