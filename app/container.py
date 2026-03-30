"""
Контейнер dishka для управления зависимостями приложения.

Определяет провайдеры для:
- Application scope: конфигурация, менеджеры (создаются один раз при старте)
- Request scope: сессии БД, сервисы (создаются для каждого запроса)
"""

from typing import Iterator

import httpx
from dishka import Provider, Scope, make_container, provide
from sqlalchemy.orm import Session as SQLAlchemySession

from app.config.settings import AppConfig, get_config
from app.core.camera.manager import CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.ptz.manager import PTZCameraManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.services.auto_ptz_service import AutoPTZService
from app.services.camera_gateway_client import CameraGatewayClient
from app.services.camera_service import CameraService
from app.services.ptz_service import PTZService


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


class ServicesProvider(Provider):
    """Провайдер для сервисного слоя."""

    @provide(scope=Scope.APP)
    def get_gateway_http_client(self, config: AppConfig) -> Iterator[httpx.Client]:
        headers: dict[str, str] = {}
        if getattr(config, "camera_api_token", None):
            headers["Authorization"] = f"Bearer {config.camera_api_token}"

        client = httpx.Client(
            base_url=config.camera_api_base_url.rstrip("/"),
            headers=headers,
            timeout=10.0,
            trust_env=False
        )
        try:
            yield client
        finally:
            client.close()

    @provide(scope=Scope.APP)
    def get_camera_gateway_client(self, client: httpx.Client) -> CameraGatewayClient:
        return CameraGatewayClient(client=client)

    @provide(scope=Scope.APP)
    def get_camera_service(
        self,
        camera_manager: CameraManager,
        ptz_manager: PTZCameraManager,
        auto_ptz_manager: AutoPTZManager,
        detector_manager: DetectorManager,
        config: AppConfig,
        camera_gateway: CameraGatewayClient,
    ) -> CameraService:
        """
        CameraService — APP scope, т.к. хранит состояние воркера
        (_worker_thread, _stop_event, _selected_camera_id),
        которое должно пережить отдельный HTTP-запрос.
        Все зависимости уже APP scope
        """
        return CameraService(
            camera_manager=camera_manager,
            ptz_manager=ptz_manager,
            auto_ptz_manager=auto_ptz_manager,
            detector_manager=detector_manager,
            config=config,
            camera_gateway=camera_gateway,
        )

    @provide(scope=Scope.REQUEST)
    def get_ptz_service(
        self,
        ptz_manager: PTZCameraManager,
        config: AppConfig,
        camera_gateway: CameraGatewayClient,
        camera_service: CameraService,
    ) -> PTZService:
        """Создаёт PTZService для каждого запроса."""
        return PTZService(
            ptz_manager=ptz_manager,
            config=config,
            camera_gateway=camera_gateway,
            camera_service=camera_service,
        )

    @provide(scope=Scope.REQUEST)
    def get_auto_ptz_service(
        self,
        auto_ptz_manager: AutoPTZManager,
        ptz_manager: PTZCameraManager,
        camera_gateway: CameraGatewayClient,
    ) -> AutoPTZService:
        """Создаёт AutoPTZService для каждого запроса."""
        return AutoPTZService(
            auto_ptz_manager=auto_ptz_manager,
            ptz_manager=ptz_manager,
            camera_gateway=camera_gateway,
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
        ServicesProvider(),
    )
