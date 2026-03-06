from typing import List

from fastapi import APIRouter, HTTPException
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaSyncRoute

from app.schemas.camera import (
    CameraResponse,
    CreateCamera,
    CreateCameraResponse,
    UpdateCamera,
)
from app.services import CameraService
from app.utils.uow import InterfaceUnitOfWork

router = APIRouter(prefix="/api", tags=["cameras"], route_class=DishkaSyncRoute)


@router.get("/cameras")
def list_cameras(
    uow: FromDishka[InterfaceUnitOfWork],
    camera_service: FromDishka[CameraService],
) -> List[CameraResponse]:
    return camera_service.list_cameras(uow)


@router.post("/camera")
def create_camera(
    uow: FromDishka[InterfaceUnitOfWork],
    camera: CreateCamera,
    camera_service: FromDishka[CameraService],
) -> CreateCameraResponse:
    """
    Создать новую камеру в конфиге.
    """
    return camera_service.create_camera(uow, camera)


@router.patch("/camera/{camera_id}")
def patch_camera(
    camera_id: int,
    uow: FromDishka[InterfaceUnitOfWork],
    camera: UpdateCamera,
    camera_service: FromDishka[CameraService],
):
    """
    Обновить данные камеры.
    """
    camera_response = camera_service.update_camera(uow, camera_id, camera)
    if camera_response is None:
        raise HTTPException(status_code=404, detail="Camera not found or not enabled")
    return camera_response


@router.delete("/camera/{camera_id}")
def soft_delete_camera(
    camera_id: int,
    uow: FromDishka[InterfaceUnitOfWork],
    camera_service: FromDishka[CameraService],
):
    """
    Пометить камеру как удалённую в конфиге.
    """

    camera = camera_service.soft_delete_camera(uow, camera_id)

    if camera is False:
        return HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.get("/camera/{camera_id}")
def one_camera(
    uow: FromDishka[InterfaceUnitOfWork],
    camera_id: int,
    camera_service: FromDishka[CameraService],
) -> CameraResponse:
    camera_response = camera_service.get_camera_by_id(uow, camera_id)

    if camera_response is None:
        raise HTTPException(status_code=404, detail="Camera not found or not enabled")
    return camera_response
