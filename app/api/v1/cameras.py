from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_token, get_camera_service
from app.services import CameraService
from .dependencies import UOWDep

router = APIRouter(prefix="/api", tags=["cameras"])


@router.get("/cameras")
def list_cameras(
    # _token: str = Depends(get_token),
    uow: UOWDep,
    camera_service: CameraService = Depends(get_camera_service),
):
    """
    Вернуть список всех камер из конфига.
    Формат:
    {
      "camera1": {...},
      "camera2": {...}
    }
    """
    return camera_service.list_cameras(uow)
