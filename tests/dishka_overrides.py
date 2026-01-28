"""
Вспомогательные функции для переопределения зависимостей dishka в тестах.

Этот модуль предоставляет удобные способы подмены зависимостей
в контейнере dishka для изолированного тестирования.
"""
from typing import Any, Callable
from unittest.mock import MagicMock

from dishka import Provider, Scope, make_container, provide
from dishka.integrations.fastapi import setup_dishka

from app.container import ConfigProvider, ServicesProvider
from app.core.camera.manager import CameraManager
from app.core.ptz.manager import PTZCameraManager


class MockManagersProvider(Provider):
    """
    Провайдер для мок-объектов менеджеров в тестах.
    
    Использование:
        provider = MockManagersProvider(
            camera_manager_mock=mock_camera_manager,
            ptz_manager_mock=mock_ptz_manager
        )
    """
    
    def __init__(
        self,
        camera_manager_mock: CameraManager = None,
        ptz_manager_mock: PTZCameraManager = None,
    ):
        super().__init__()
        self._camera_manager_mock = camera_manager_mock or MagicMock(spec=CameraManager)
        self._ptz_manager_mock = ptz_manager_mock or MagicMock(spec=PTZCameraManager)
    
    @provide(scope=Scope.APP)
    def get_camera_manager(self) -> CameraManager:
        """Возвращает мок CameraManager."""
        return self._camera_manager_mock
    
    @provide(scope=Scope.APP)
    def get_ptz_camera_manager(self) -> PTZCameraManager:
        """Возвращает мок PTZCameraManager."""
        return self._ptz_manager_mock


def create_test_app_with_mocks(
    test_db_session_factory,
    camera_manager_mock: CameraManager = None,
    ptz_manager_mock: PTZCameraManager = None,
):
    """
    Создаёт тестовое FastAPI приложение с мок-зависимостями.
    
    Args:
        test_db_session_factory: Фабрика сессий тестовой БД
        camera_manager_mock: Мок для CameraManager (опционально)
        ptz_manager_mock: Мок для PTZCameraManager (опционально)
    
    Returns:
        FastAPI приложение с настроенными моками
    
    Пример:
        app = create_test_app_with_mocks(
            test_db_session_factory,
            ptz_manager_mock=my_mock
        )
        client = TestClient(app)
    """
    from fastapi import FastAPI
    from sqlalchemy.orm import Session as SQLAlchemySession
    
    from app.utils.uow import InterfaceUnitOfWork, UnitOfWork
    
    # Тестовый провайдер БД
    class TestDatabaseProvider(Provider):
        @provide(scope=Scope.REQUEST)
        def get_db_session(self) -> SQLAlchemySession:
            session = test_db_session_factory()
            try:
                yield session
            finally:
                session.close()
        
        @provide(scope=Scope.REQUEST)
        def get_uow(self, session: SQLAlchemySession) -> InterfaceUnitOfWork:
            uow = UnitOfWork()
            uow.session_factory = lambda: session
            return uow
    
    # Создаём контейнер с моками
    container = make_container(
        ConfigProvider(),
        MockManagersProvider(
            camera_manager_mock=camera_manager_mock,
            ptz_manager_mock=ptz_manager_mock,
        ),
        TestDatabaseProvider(),
        ServicesProvider(),
    )
    
    # Создаём приложение
    app = FastAPI(title="PTZ Test", version="1.0.0-test")
    setup_dishka(container, app)
    
    # Добавляем роутеры
    from app.api.v1.cameras import router as cameras_router
    from app.api.v1.ptz import router as ptz_router
    from app.api.v1.streams import router as streams_router
    
    app.include_router(cameras_router)
    app.include_router(streams_router)
    app.include_router(ptz_router)
    
    # Регистрируем обработчики ошибок
    from app.main import register_exception_handlers
    register_exception_handlers(app)
    
    return app, container
