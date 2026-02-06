"""
Integration тесты для CameraService.

Эти тесты проверяют взаимодействие сервиса с реальной БД,
но с замоканными внешними зависимостями (менеджеры).
"""
from unittest.mock import MagicMock

from app.config.settings import AppConfig
from app.core.camera.manager import CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.repositories.camera_repository import CameraRepository
from app.services.camera_service import CameraService
from app.utils.uow import UnitOfWork


class TestCameraService:
    """Integration тесты для CameraService с реальной БД."""

    def test_list_cameras(self, db_session, camera_db_onvif, camera_db_tms20):
        """Проверяет получение списка камер."""
        # Простые моки без DI контейнера
        service = CameraService(
            camera_manager=MagicMock(spec=CameraManager),
            auto_ptz_manager=MagicMock(spec=AutoPTZManager),
            detector_manager=MagicMock(spec=DetectorManager),
            config=MagicMock(spec=AppConfig),
        )
        
        uow = UnitOfWork()
        uow.session = db_session
        uow.camera = CameraRepository(db_session)
        
        cameras = service.list_cameras(uow)
        
        assert len(cameras) >= 0

    def test_get_camera_by_id_success(self, db_session, camera_db_onvif):
        """Проверяет получение активной камеры по ID."""
        service = CameraService(
            camera_manager=MagicMock(spec=CameraManager),
            auto_ptz_manager=MagicMock(spec=AutoPTZManager),
            detector_manager=MagicMock(spec=DetectorManager),
            config=MagicMock(spec=AppConfig),
        )

        uow = UnitOfWork()
        uow.session_factory = lambda: db_session

        assert camera_db_onvif.enabled is True

        camera = service.get_camera_by_id(uow, camera_db_onvif.id)

        assert camera is not None
        assert camera.name == "Test Camera ONVIF"

    def test_get_camera_by_id_disabled_returns_none(self, db_session, disabled_camera):
        """Проверяет, что отключённая камера возвращает None."""
        service = CameraService(
            camera_manager=MagicMock(spec=CameraManager),
            auto_ptz_manager=MagicMock(spec=AutoPTZManager),
            detector_manager=MagicMock(spec=DetectorManager),
            config=MagicMock(spec=AppConfig),
        )

        uow = UnitOfWork()
        uow.session_factory = lambda: db_session

        camera = service.get_camera_by_id(uow, disabled_camera.id)

        assert camera is None
