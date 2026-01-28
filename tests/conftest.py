import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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

from app.main import create_app
from app.models.base import Base
from app.models.camera import Camera
from app.models.camera_connection import CameraConnection
from app.models.camera_location import CameraLocation
from app.models.camera_ptz import CameraPTZ
from app.models.ptz_types import PTZType


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
    """
    FastAPI приложение для тестов.
    
    Создаёт приложение с тестовым контейнером dishka,
    который использует тестовую БД вместо production БД.
    """
    from dishka import make_container, Provider, provide, Scope
    from dishka.integrations.fastapi import setup_dishka
    from app.container import (
        ConfigProvider, 
        ManagersProvider, 
        ServicesProvider
    )
    from app.utils.uow import UnitOfWork, InterfaceUnitOfWork
    from sqlalchemy.orm import Session as SQLAlchemySession
    from app.config.settings import AppConfig, CameraConfig
    
    # Создаём провайдер для тестовой БД
    class TestDatabaseProvider(Provider):
        """Провайдер, который использует тестовую БД вместо production."""
        
        @provide(scope=Scope.REQUEST)
        def get_db_session(self) -> Iterator[SQLAlchemySession]:
            """Возвращает сессию из тестовой БД."""
            session = test_db_session_factory()
            try:
                yield session
            finally:
                session.close()
        
        @provide(scope=Scope.REQUEST)
        def get_uow(self, session: SQLAlchemySession) -> InterfaceUnitOfWork:
            """Создаёт UnitOfWork с тестовой сессией."""
            uow = UnitOfWork()
            uow.session_factory = lambda: session
            return uow
    
    # Создаём провайдер тестовой конфигурации
    class TestConfigProvider(Provider):
        """Провайдер конфигурации для тестов."""
        
        @provide(scope=Scope.APP)
        def get_test_config(self) -> AppConfig:
            """
            Возвращает тестовую конфигурацию.
            Камеры загружаются из тестовой БД.
            """
            from app.repositories.camera_repository import CameraRepository
            
            # Создаём базовую конфигурацию
            config = AppConfig()
            
            # Загружаем камеры из тестовой БД
            session = test_db_session_factory()
            try:
                repo = CameraRepository(session)
                cameras = repo.get_all_cameras(enabled_only=True)
                
                # Конвертируем в CameraConfig
                cameras_dict = {}
                for camera in cameras:
                    cameras_dict[camera.id] = CameraConfig.from_db_model(camera)
                
                config.cameras = cameras_dict
            finally:
                session.close()
            
            return config
    
    # Создаём тестовый контейнер
    test_container = make_container(
        TestConfigProvider(),  # используем тестовый конфиг
        ManagersProvider(),
        TestDatabaseProvider(),  # используем тестовый провайдер БД
        ServicesProvider(),
    )
    
    # Создаём приложение БЕЗ вызова create_app(),
    # чтобы избежать двойной инициализации
    from fastapi import FastAPI
    app_instance = FastAPI(
        title="PTZ Backend Test",
        version="1.0.0-test",
    )
    
    # Настраиваем dishka с тестовым контейнером
    setup_dishka(test_container, app_instance)
    
    # Добавляем роутеры
    from app.api.v1.cameras import router as cameras_router
    from app.api.v1.ptz import router as ptz_router
    from app.api.v1.streams import router as streams_router
    
    app_instance.include_router(cameras_router)
    app_instance.include_router(streams_router)
    app_instance.include_router(ptz_router)
    
    # Регистрируем обработчики ошибок
    from app.main import register_exception_handlers
    register_exception_handlers(app_instance)
    
    yield app_instance
    
    # Cleanup: закрываем контейнер после всех тестов
    test_container.close()

@pytest.fixture
def client(app):
    """HTTP клиент для тестирования API."""
    return TestClient(app)


@pytest.fixture
def app_with_mocks(test_db, test_db_session_factory):
    """
    Создаёт приложение с моками для unit/integration тестов.
    
    Используйте этот фикстур когда нужно:
    - Мокировать менеджеры (CameraManager, PTZCameraManager, AutoPTZManager)
    - Тестировать сервисы через dishka DI
    
    Возвращает tuple: (app, container, mocks_dict)
    где mocks_dict содержит: {'camera_manager', 'ptz_manager', 'auto_ptz_manager'}
    
    ВАЖНО: Используйте тот же test_db, что и в db_session фикстуре,
    чтобы тестовые данные были видны сервисам.
    """
    from unittest.mock import MagicMock
    from tests.dishka_overrides import create_test_app_with_mocks
    from app.core.camera.manager import CameraManager
    from app.core.ptz.manager import PTZCameraManager
    from app.core.tracking.auto_ptz_manager import AutoPTZManager
    
    # Создаём моки
    camera_manager_mock = MagicMock(spec=CameraManager)
    ptz_manager_mock = MagicMock(spec=PTZCameraManager)
    auto_ptz_manager_mock = MagicMock(spec=AutoPTZManager)
    
    # Создаём приложение с моками
    app_instance, container = create_test_app_with_mocks(
        test_db_session_factory,
        camera_manager_mock=camera_manager_mock,
        ptz_manager_mock=ptz_manager_mock,
        auto_ptz_manager_mock=auto_ptz_manager_mock,
    )
    
    mocks = {
        'camera_manager': camera_manager_mock,
        'ptz_manager': ptz_manager_mock,
        'auto_ptz_manager': auto_ptz_manager_mock,
    }
    
    yield app_instance, container, mocks
    
    # Cleanup
    container.close()


@pytest.fixture
def client_with_mocks(app_with_mocks):
    """HTTP клиент с моками для тестирования."""
    app_instance, container, mocks = app_with_mocks
    client = TestClient(app_instance)
    # Возвращаем клиент и моки для удобства
    return client, mocks


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
