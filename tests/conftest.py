import os
import sys
from pathlib import Path
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLSession
from sqlalchemy.pool import StaticPool

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
os.environ["CAMERAS"] = ""  # Пусто, так как будем загружать из БД

from app.models.base import Base
from app.db.session import Session
from app.models.ptz_types import PTZType
from app.models.camera import Camera
from app.models.camera_connection import CameraConnection
from app.models.camera_location import CameraLocation
from app.models.camera_ptz import CameraPTZ
from app.main import create_app


@pytest.fixture(scope="session")
def test_db():
    """
    Создаёт in-memory SQLite БД для тестов.
    Используется во всей сессии тестирования.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Создаём все таблицы
    Base.metadata.create_all(engine)
    
    # Инициализируем справочные данные (PTZ типы)
    TestSession = sessionmaker(bind=engine)
    db_session = TestSession()
    
    ptz_types = [
        PTZType(type="onvif"),
        PTZType(type="tms20"),
    ]
    db_session.add_all(ptz_types)
    db_session.commit()
    db_session.close()
    
    return engine


@pytest.fixture(scope="session")
def test_db_session_factory(test_db):
    """Фабрика сессий для тестовой БД."""
    return sessionmaker(bind=test_db)


@pytest.fixture
def db_session(test_db_session_factory):
    """Сессия БД для одного теста с автоматическим откатом."""
    session = test_db_session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def app(test_db, test_db_session_factory):
    """FastAPI приложение для тестов."""
    app_instance = create_app()
    return app_instance


@pytest.fixture
def client(app):
    """HTTP клиент для тестирования API."""
    return TestClient(app)


@pytest.fixture
def auth_header():
    """Bearer токен для авторизации."""
    token = os.getenv("APP_TOKEN", "test-token-123")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def invalid_auth_header():
    """Невалидный токен."""
    return {"Authorization": "Bearer invalid-token"}


# --- Camera Fixtures ---

@pytest.fixture
def camera_db_onvif(db_session):
    """Создаёт ONVIF камеру в БД."""
    ptz_type_obj = db_session.query(PTZType).filter_by(type="onvif").first()
    
    camera = Camera(
        name="Test Camera ONVIF",
        enabled=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    connection = CameraConnection(
        host="192.168.1.100",
        port=8080,
        rtsp_url="rtsp://192.168.1.100:554/stream1",
        rtsp_url_ik="rtsp://192.168.1.100:554/stream2",
        username="admin",
        password="password123",
    )
    
    location = CameraLocation(
        lat=55.751244,
        lon=37.618423,
        height=15.5,
        rate=0.0,
    )
    
    ptz = CameraPTZ(
        type_id=ptz_type_obj.id,
    )
    
    camera.connection = connection
    camera.location = location
    camera.ptz = ptz
    
    db_session.add(camera)
    db_session.commit()
    
    return camera


@pytest.fixture
def camera_db_tms20(db_session):
    """Создаёт TMS-20 камеру в БД."""
    ptz_type_obj = db_session.query(PTZType).filter_by(type="tms20").first()
    
    camera = Camera(
        name="Test Camera TMS-20",
        enabled=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    connection = CameraConnection(
        host="192.168.1.101",
        port=1470,
        rtsp_url="rtsp://192.168.1.101:554/stream1",
        rtsp_url_ik="rtsp://192.168.1.101:554/stream2",
        username="admin",
        password="password123",
    )
    
    location = CameraLocation(
        lat=55.755814,
        lon=37.617635,
        height=12.0,
        rate=10.0,
    )
    
    ptz = CameraPTZ(
        type_id=ptz_type_obj.id,
    )
    
    camera.connection = connection
    camera.location = location
    camera.ptz = ptz
    
    db_session.add(camera)
    db_session.commit()
    
    return camera


@pytest.fixture
def disabled_camera(db_session):
    """Создаёт отключённую камеру."""
    ptz_type_obj = db_session.query(PTZType).filter_by(type="onvif").first()
    
    camera = Camera(
        name="Disabled Camera",
        enabled=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    connection = CameraConnection(
        host="192.168.1.200",
        port=8080,
        rtsp_url="rtsp://192.168.1.200:554/stream1",
        rtsp_url_ik="rtsp://192.168.1.200:554/stream2",
        username="admin",
        password="password123",
    )
    
    location = CameraLocation(
        lat=55.0,
        lon=37.0,
        height=10.0,
        rate=0.0,
    )
    
    ptz = CameraPTZ(
        type_id=ptz_type_obj.id,
    )
    
    camera.connection = connection
    camera.location = location
    camera.ptz = ptz
    
    db_session.add(camera)
    db_session.commit()
    
    return camera


@pytest.fixture
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
        lat=55.751244,
        lon=37.618423,
        height=15.5,
        rate=0.0,
        ptz_type="onvif",
    )


@pytest.fixture
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
        lat=55.755814,
        lon=37.617635,
        height=12.0,
        rate=10.0,
        ptz_type="tms20",
    )