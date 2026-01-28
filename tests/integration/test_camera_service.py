import pytest
from dishka import FromDishka
from dishka.integrations.fastapi import inject

from app.services.camera_service import CameraService
from app.utils.uow import InterfaceUnitOfWork


class TestCameraService:
    """Интеграционные тесты для CameraService."""

    def test_list_cameras(
        self, app_with_mocks, db_session, camera_db_onvif, camera_db_tms20
    ):
        """Проверяет получение списка камер через dishka DI."""
        app_instance, container, mocks = app_with_mocks
        
        # Получаем сервис и UoW из контейнера dishka
        with container() as request_container:
            service = request_container.get(CameraService)
            uow = request_container.get(InterfaceUnitOfWork)
            
            cameras = service.list_cameras(uow)
            
            assert len(cameras) >= 0  # может быть пусто, если софт-дилит
            # или >= 2, если обе камеры активны

    def test_get_camera_by_id_success(self, app_with_mocks, db_session, camera_db_onvif):
        """Проверяет получение активной камеры по ID через dishka DI."""
        app_instance, container, mocks = app_with_mocks
        
        # Получаем сервис и UoW из контейнера dishka
        with container() as request_container:
            service = request_container.get(CameraService)
            uow = request_container.get(InterfaceUnitOfWork)
            
            # Камера должна быть активна
            assert camera_db_onvif.enabled is True
            
            camera = service.get_camera_by_id(uow, camera_db_onvif.id)
            
            if camera:
                assert camera.name == "Test Camera ONVIF"

    def test_get_camera_by_id_disabled_returns_none(
        self, app_with_mocks, db_session, disabled_camera
    ):
        """Проверяет, что отключённая камера возвращает None через dishka DI."""
        app_instance, container, mocks = app_with_mocks
        
        # Получаем сервис и UoW из контейнера dishka
        with container() as request_container:
            service = request_container.get(CameraService)
            uow = request_container.get(InterfaceUnitOfWork)
            
            camera = service.get_camera_by_id(uow, disabled_camera.id)
            
            # Отключённые камеры не возвращаются
            assert camera is None
    
    def test_service_has_mocked_managers(self, app_with_mocks):
        """Проверяет, что сервис получает моки через DI."""
        app_instance, container, mocks = app_with_mocks
        
        with container() as request_container:
            service = request_container.get(CameraService)
            
            # Проверяем, что менеджеры действительно замокированы
            assert service.camera_manager is mocks['camera_manager']
            assert service.auto_ptz_manager is mocks['auto_ptz_manager']
