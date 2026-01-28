"""
Sync dependency functions для работы с Dishka контейнером.
"""
from fastapi import Request
from typing import Annotated

from app.services.camera_service import CameraService
from app.services.ptz_service import PTZService
from app.utils.uow import InterfaceUnitOfWork
from app.core.tracking.auto_ptz_manager import AutoPTZManager


def get_uow(request: Request) -> InterfaceUnitOfWork:
    """Получить UnitOfWork из sync Dishka контейнера."""
    return request.state.dishka_container.get(InterfaceUnitOfWork)


def get_camera_service(request: Request) -> CameraService:
    """Получить CameraService из sync Dishka контейнера."""
    return request.state.dishka_container.get(CameraService)


def get_ptz_service(request: Request) -> PTZService:
    """Получить PTZService из sync Dishka контейнера."""
    return request.state.dishka_container.get(PTZService)


def get_auto_ptz_manager(request: Request) -> AutoPTZManager:
    """Получить AutoPTZManager из sync Dishka контейнера."""
    return request.state.dishka_container.get(AutoPTZManager)
