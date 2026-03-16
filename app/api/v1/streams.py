# app/api/v1/streams.py

from fastapi import APIRouter, Depends, HTTPException, Header
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaSyncRoute

from app.api.v1.deps import get_client_id
from app.services import CameraService

router = APIRouter(prefix="/api", tags=["streams"], route_class=DishkaSyncRoute)


@router.post("/camera/select/{camera_id}/")
def select_camera(
    camera_id: int,
    camera_service: FromDishka[CameraService],
    client_id: str = Depends(get_client_id)
):
    """
    Фронт сообщает выбранную камеру.
    Бэк запоминает выбор и запускает фоновую обработку RTSP (детект/трек + сокеты).
    """
    camera_service.select_camera(
        camera_id, client_id, enable_detection=True, enable_auto_tracking=True
    )
    return {"selected_camera_id": camera_id}


@router.post("/camera/stop/")
def stop_selected_camera(
    camera_service: FromDishka[CameraService],
    client_id: str = Depends(get_client_id),
):
    camera_service.stop_selected_camera(client_id)
    return {"stopped": True}
