# app/api/v1/streams.py

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_camera_service
from app.services import CameraService

router = APIRouter(prefix="/api", tags=["streams"])


@router.post("/camera/select/{camera_id}")
def select_camera(
    camera_id: int,
    camera_service: CameraService = Depends(get_camera_service),
):
    """
    Фронт сообщает выбранную камеру.
    Бэк запоминает выбор и запускает фоновую обработку RTSP (детект/трек + сокеты).
    """
    camera_service.select_camera(
        camera_id, enable_detection=True, enable_auto_tracking=True
    )
    return {"selected_camera_id": camera_id}


@router.post("/camera/stop")
def stop_selected_camera(
    camera_service: CameraService = Depends(get_camera_service),
):
    camera_service.stop_selected_camera()
    return {"stopped": True}
