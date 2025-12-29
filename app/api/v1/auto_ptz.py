from fastapi import APIRouter
from pydantic import BaseModel

from app.core.tracking.auto_ptz_manager import auto_ptz_manager

router = APIRouter(prefix="/api", tags=["auto-ptz"])


class TrackRequest(BaseModel):
    track_id: int


@router.post("/track/{camera_id}")
def start_auto_tracking(camera_id: str, body: TrackRequest):
    """
    Включить слежение за объектом с указанным track_id.
    """
    auto_ptz_manager.set_target(camera_id, body.track_id)
    return {"status": "ok", "camera_id": camera_id, "track_id": body.track_id}


@router.post("/stop/{camera_id}")
def stop_auto_tracking(camera_id: str):
    """
    Выключить автослежение для камеры.
    """
    auto_ptz_manager.clear_target(camera_id)
    return {"status": "ok", "camera_id": camera_id}


@router.get("/status/{camera_id}")
def get_auto_tracking_status(camera_id: str):
    """
    Получить текущий выбранный track_id (если есть).
    """
    track_id = auto_ptz_manager.get_target(camera_id)
    return {"status": "ok", "camera_id": camera_id, "track_id": track_id}
