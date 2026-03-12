from __future__ import annotations

from typing import Mapping
from unittest.mock import MagicMock

from dishka import Provider, Scope, make_container, provide
from dishka.integrations.fastapi import setup_dishka

from app.container import ConfigProvider, ServicesProvider
from app.config.settings import CameraConfig, DetectorMode
from app.core.camera.manager import CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.ptz.manager import PTZCameraManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.services.camera_gateway_client import CameraGatewayClient


class MockManagersProvider(Provider):
    """
    Провайдер для мок-объектов менеджеров в тестах.

    Использование:
        provider = MockManagersProvider(
            camera_manager_mock=mock_camera_manager,
            ptz_manager_mock=mock_ptz_manager,
            auto_ptz_manager_mock=mock_auto_ptz_manager,
            detector_manager_mock=mock_detector_manager,
        )
    """

    def __init__(
        self,
        camera_manager_mock: CameraManager = None,
        ptz_manager_mock: PTZCameraManager = None,
        auto_ptz_manager_mock: AutoPTZManager = None,
        detector_manager_mock: DetectorManager = None,
    ):
        super().__init__()
        self._camera_manager_mock = camera_manager_mock or MagicMock(spec=CameraManager)
        self._ptz_manager_mock = ptz_manager_mock or MagicMock(spec=PTZCameraManager)
        self._auto_ptz_manager_mock = auto_ptz_manager_mock or MagicMock(
            spec=AutoPTZManager
        )
        self._detector_manager_mock = detector_manager_mock or MagicMock(
            spec=DetectorManager
        )

    @provide(scope=Scope.APP)
    def get_camera_manager(self) -> CameraManager:
        """Возвращает мок CameraManager."""
        return self._camera_manager_mock

    @provide(scope=Scope.APP)
    def get_ptz_camera_manager(self) -> PTZCameraManager:
        """Возвращает мок PTZCameraManager."""
        return self._ptz_manager_mock

    @provide(scope=Scope.APP)
    def get_detector_manager(self) -> DetectorManager:
        """Возвращает мок DetectorManager."""
        return self._detector_manager_mock

    @provide(scope=Scope.APP)
    def get_auto_ptz_manager(self) -> AutoPTZManager:
        """Возвращает мок AutoPTZManager."""
        return self._auto_ptz_manager_mock


def create_test_app_with_mocks(
    *,
    camera_configs: Mapping[int, CameraConfig] | None = None,
    camera_manager_mock: CameraManager = None,
    ptz_manager_mock: PTZCameraManager = None,
    auto_ptz_manager_mock: AutoPTZManager = None,
    detector_manager_mock: DetectorManager = None,
):
    """
    Создаёт тестовое FastAPI приложение с мок-зависимостями.

    Args:
        camera_configs: In-memory "каталог" камер для gateway, key=id.
        camera_manager_mock: Мок для CameraManager (опционально).
        ptz_manager_mock: Мок для PTZCameraManager (опционально).
        auto_ptz_manager_mock: Мок для AutoPTZManager (опционально).
        detector_manager_mock: Мок для DetectorManager (опционально).

    Returns:
        FastAPI приложение с настроенными моками

    Пример:
        app, container = create_test_app_with_mocks(
            camera_configs={1: cfg1, 2: cfg2},
            ptz_manager_mock=my_mock,
        )
    """
    from fastapi import FastAPI

    class TestGatewayProvider(Provider):
        @provide(scope=Scope.APP)
        def get_camera_gateway_client(self) -> CameraGatewayClient:
            """
            В тестах не ходим в реальный API gateway.
            Эмулируем gateway: выдаём CameraConfig из in-memory словаря.
            """

            gateway = MagicMock(spec=CameraGatewayClient)
            cfgs = dict(camera_configs or {})

            def _get_by_id(camera_id: int):
                return cfgs.get(camera_id)

            gateway.get_camera_config_by_id.side_effect = _get_by_id
            gateway.get_nearest_camera_config.return_value = None
            return gateway

    class DefaultDetectorMockProvider(Provider):
        """
        На случай, если в тестах не передали detector_manager_mock:
        даём детектор с безопасными дефолтами (без загрузки весов).
        """

        @provide(scope=Scope.APP)
        def get_detector_manager(self) -> DetectorManager:
            mgr = detector_manager_mock or MagicMock(spec=DetectorManager)
            mgr.get_current_mode.return_value = DetectorMode.OPTICAL
            mgr.get_available_modes.return_value = {
                "optical": {"available": True, "weights_path": "optical.pt"},
                "thermal": {"available": True, "weights_path": "thermal.pt"},
            }
            mgr.switch_mode.side_effect = lambda mode: mode
            return mgr

    # Создаём контейнер с моками
    container = make_container(
        ConfigProvider(),
        MockManagersProvider(
            camera_manager_mock=camera_manager_mock,
            ptz_manager_mock=ptz_manager_mock,
            auto_ptz_manager_mock=auto_ptz_manager_mock,
            detector_manager_mock=detector_manager_mock,
        ),
        ServicesProvider(),
        TestGatewayProvider(),
        DefaultDetectorMockProvider(),
    )

    # Создаём приложение
    app = FastAPI(title="PTZ Test", version="1.0.0-test")
    setup_dishka(container, app)

    # Добавляем роутеры
    from app.api.v1.ptz import router as ptz_router
    from app.api.v1.streams import router as streams_router
    from app.api.v1.auto_ptz import router as auto_ptz_router
    from app.api.v1.detector import router as detector_router

    app.include_router(streams_router)
    app.include_router(ptz_router)
    app.include_router(auto_ptz_router)
    app.include_router(detector_router)

    # Регистрируем обработчики ошибок
    from app.main import register_exception_handlers

    register_exception_handlers(app)

    return app, container
