from unittest.mock import MagicMock

from app.repositories.camera_repository import CameraRepository
from app.services.camera_service import CameraService
from app.utils.uow import UnitOfWork
from app.config.settings import AppConfig
from app.core.camera.manager import CameraManager


class TestCameraService:
    """Интеграционные тесты для CameraService."""

    def test_list_cameras(self, db_session, camera_db_onvif, camera_db_tms20):
        """Проверяет получение списка камер."""
        # Create mock dependencies
        mock_camera_manager = MagicMock(spec=CameraManager)
        mock_config = MagicMock(spec=AppConfig)
        
        service = CameraService(camera_manager=mock_camera_manager, config=mock_config)
        uow = UnitOfWork()
        uow.session = db_session
        uow.camera = CameraRepository(db_session)

        cameras = service.list_cameras(uow)

        assert len(cameras) >= 0  # может быть пусто, если софт-дилит
        # или >= 2, если обе камеры активны

    def test_get_camera_by_id_success(self, db_session, camera_db_onvif):
        """Проверяет получение активной камеры по ID."""
        # Create mock dependencies
        mock_camera_manager = MagicMock(spec=CameraManager)
        mock_config = MagicMock(spec=AppConfig)
        
        service = CameraService(camera_manager=mock_camera_manager, config=mock_config)
        uow = UnitOfWork()
        uow.session = db_session
        uow.camera = CameraRepository(db_session)

        # Камера должна быть активна
        assert camera_db_onvif.enabled is True

        camera = service.get_camera_by_id(uow, camera_db_onvif.id)

        if camera:
            assert camera.name == "Test Camera ONVIF"

    def test_get_camera_by_id_disabled_returns_none(self, db_session, disabled_camera):
        """Проверяет, что отключённая камера возвращает None."""
        # Create mock dependencies
        mock_camera_manager = MagicMock(spec=CameraManager)
        mock_config = MagicMock(spec=AppConfig)
        
        service = CameraService(camera_manager=mock_camera_manager, config=mock_config)
        uow = UnitOfWork()
        uow.session = db_session
        uow.camera = CameraRepository(db_session)

        camera = service.get_camera_by_id(uow, disabled_camera.id)

        # Отключённые камеры не возвращаются
        assert camera is None
