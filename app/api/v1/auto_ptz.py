from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaSyncRoute

from app.api.v1.deps import get_client_id
from app.schemas.auto_ptz import TrackRequest
from app.services import AutoPTZService

router = APIRouter(prefix="/api", tags=["auto-ptz"], route_class=DishkaSyncRoute)


@router.post("/track/{camera_id}")
def start_auto_tracking(
    camera_id: int,
    body: TrackRequest,
    auto_ptz_service: FromDishka[AutoPTZService],
    client_id: str = Depends(get_client_id)
):
    """Включить слежение за объектом с указанным track_id."""
    auto_ptz_service.set_target(camera_id, body.track_id, client_id=client_id)
    return {"status": "ok", "camera_id": camera_id, "track_id": body.track_id}


@router.post("/stop/{camera_id}")
def stop_auto_tracking(
    camera_id: int,
    auto_ptz_service: FromDishka[AutoPTZService],
    client_id: str = Depends(get_client_id)
):
    """Выключить автослежение для камеры."""
    auto_ptz_service.clear_target(camera_id, client_id=client_id)
    return {"status": "ok", "camera_id": camera_id}


@router.get("/status/{camera_id}")
def get_auto_tracking_status(
    camera_id: int,
    auto_ptz_service: FromDishka[AutoPTZService],
    client_id: str = Depends(get_client_id),
):
    """Получить текущий выбранный track_id (если есть)."""
    track_id = auto_ptz_service.get_target(camera_id, client_id=client_id)
    return {"status": "ok", "camera_id": camera_id, "track_id": track_id}
