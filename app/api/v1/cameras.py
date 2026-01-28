from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies import get_camera_service, get_uow
from app.schemas.camera import (
    CameraResponse,
    CreateCamera,
    CreateCameraResponse,
    UpdateCamera,
)
from app.services import CameraService
from app.utils.uow import InterfaceUnitOfWork

router = APIRouter(prefix="/api", tags=["cameras"])


@router.get("/cameras")
def list_cameras(
    uow: Annotated[InterfaceUnitOfWork, Depends(get_uow)],
    camera_service: Annotated[CameraService, Depends(get_camera_service)],
) -> List[CameraResponse]:
    """
    Вернуть список всех камер из конфига.
    Формат:
    {
      "camera1": {...},
      "camera2": {...}
    }
    """
    return camera_service.list_cameras(uow)


@router.post("/camera")
def create_camera(
    uow: Annotated[InterfaceUnitOfWork, Depends(get_uow)],
    camera: CreateCamera,
    camera_service: Annotated[CameraService, Depends(get_camera_service)],
) -> CreateCameraResponse:
    """
    Создать новую камеру в конфиге.
    """
    return camera_service.create_camera(uow, camera)


@router.patch("/camera/{camera_id}")
def patch_camera(
    camera_id: int,
    uow: Annotated[InterfaceUnitOfWork, Depends(get_uow)],
    camera: UpdateCamera,
    camera_service: Annotated[CameraService, Depends(get_camera_service)],
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
    uow: Annotated[InterfaceUnitOfWork, Depends(get_uow)],
    camera_service: Annotated[CameraService, Depends(get_camera_service)],
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
    uow: Annotated[InterfaceUnitOfWork, Depends(get_uow)],
    camera_id: int,
    camera_service: Annotated[CameraService, Depends(get_camera_service)],
) -> CameraResponse:
    camera_response = camera_service.get_camera_by_id(uow, camera_id)

    if camera_response is None:
        raise HTTPException(status_code=404, detail="Camera not found or not enabled")
    return camera_response
