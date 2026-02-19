"""
Контейнер dishka для управления зависимостями приложения.

Определяет провайдеры для:
- Application scope: конфигурация, менеджеры (создаются один раз при старте)
- Request scope: сессии БД, сервисы (создаются для каждого запроса)
"""
from typing import Iterator

from dishka import Provider, Scope, make_container, provide
from sqlalchemy.orm import Session as SQLAlchemySession

from app.config.settings import AppConfig, get_config
from app.core.camera.manager import CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.ptz.manager import PTZCameraManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.services.camera_service import CameraService
from app.services.ptz_service import PTZService
from app.utils.uow import InterfaceUnitOfWork, UnitOfWork


class ConfigProvider(Provider):
    """Провайдер для конфигурации приложения."""
    
    @provide(scope=Scope.APP)
    def get_app_config(self) -> AppConfig:
        """
        Возвращает конфигурацию приложения.
        Использует существующую функцию get_config() с @lru_cache.
        """
        return get_config()


class ManagersProvider(Provider):
    """Провайдер для менеджеров камер, PTZ, детектора и auto-tracking."""

    @provide(scope=Scope.APP)
    def get_camera_manager(self) -> CameraManager:
        """
        Создаёт CameraManager один раз при старте приложения.
        Заменяет глобальный синглтон camera_manager.
        """
        return CameraManager()

    @provide(scope=Scope.APP)
    def get_ptz_camera_manager(self) -> PTZCameraManager:
        """
        Создаёт PTZCameraManager один раз при старте приложения.
        Заменяет глобальный синглтон ptz_camera_manager.
        """
        return PTZCameraManager()

    @provide(scope=Scope.APP)
    def get_detector_manager(self) -> DetectorManager:
        """
        Создаёт DetectorManager один раз при старте приложения.
        Конфигурация весов (optical/thermal) берётся из AppConfig.
        """
        return DetectorManager()

    @provide(scope=Scope.APP)
    def get_auto_ptz_manager(
        self,
        ptz_manager: PTZCameraManager,
    ) -> AutoPTZManager:
        """
        Создаёт AutoPTZManager один раз при старте приложения.
        Заменяет глобальный синглтон auto_ptz_manager.
        """
        return AutoPTZManager(ptz_manager=ptz_manager)


class DatabaseProvider(Provider):
    """Провайдер для работы с БД."""
    
    @provide(scope=Scope.REQUEST)
    def get_db_session(self) -> Iterator[SQLAlchemySession]:
        """
        Создаёт сессию БД для каждого запроса.
        Автоматически закрывает сессию после завершения запроса.
        """
        from app.db.session import Session
        
        session = Session()
        try:
            yield session
        finally:
            session.close()
    
    @provide(scope=Scope.REQUEST)
    def get_uow(self, session: SQLAlchemySession) -> InterfaceUnitOfWork:
        """
        Создаёт UnitOfWork для каждого запроса.
        Использует сессию из провайдера get_db_session.
        """
        uow = UnitOfWork()
        # Переопределяем session_factory, чтобы использовать уже созданную сессию
        uow.session_factory = lambda: session
        return uow


class ServicesProvider(Provider):
    """Провайдер для сервисного слоя."""
    
    @provide(scope=Scope.REQUEST)
    def get_camera_service(
        self,
        camera_manager: CameraManager,
        auto_ptz_manager: AutoPTZManager,
        detector_manager: DetectorManager,
        config: AppConfig,
    ) -> CameraService:
        """
        Создаёт CameraService для каждого запроса.
        Внедряет зависимости через конструктор.

        Примечание: camera_manager, auto_ptz_manager, detector_manager из APP scope
        автоматически доступны в REQUEST scope через dishka.
        """
        return CameraService(
            camera_manager=camera_manager,
            auto_ptz_manager=auto_ptz_manager,
            detector_manager=detector_manager,
            config=config,
        )
    
    @provide(scope=Scope.REQUEST)
    def get_ptz_service(
        self,
        ptz_manager: PTZCameraManager,
        config: AppConfig,
        uow: InterfaceUnitOfWork,
    ) -> PTZService:
        """
        Создаёт PTZService для каждого запроса.
        UoW используется для получения данных камеры из БД при каждом действии.
        """
        return PTZService(
            ptz_manager=ptz_manager,
            config=config,
            uow=uow,
        )


def create_container():
    """
    Создаёт и возвращает контейнер dishka со всеми провайдерами.
    
    Использование:
        container = create_container()
        setup_dishka(container, app)
    """
    return make_container(
        ConfigProvider(),
        ManagersProvider(),
        DatabaseProvider(),
        ServicesProvider(),
    )
