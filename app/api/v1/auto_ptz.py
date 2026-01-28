from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_auto_ptz_manager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.schemas.auto_ptz import TrackRequest

router = APIRouter(prefix="/api", tags=["auto-ptz"])


@router.post("/track/{camera_id}")
def start_auto_tracking(
    camera_id: int,
    body: TrackRequest,
    auto_ptz_manager: Annotated[AutoPTZManager, Depends(get_auto_ptz_manager)],
):
    """
    Включить слежение за объектом с указанным track_id.
    """
    auto_ptz_manager.set_target(camera_id, body.track_id)
    return {"status": "ok", "camera_id": camera_id, "track_id": body.track_id}


@router.post("/stop/{camera_id}")
def stop_auto_tracking(
    camera_id: int,
    auto_ptz_manager: Annotated[AutoPTZManager, Depends(get_auto_ptz_manager)],
):
    """
    Выключить автослежение для камеры.
    """
    auto_ptz_manager.clear_target(camera_id)
    return {"status": "ok", "camera_id": camera_id}


@router.get("/status/{camera_id}")
def get_auto_tracking_status(
    camera_id: int,
    auto_ptz_manager: Annotated[AutoPTZManager, Depends(get_auto_ptz_manager)],
):
    """
    Получить текущий выбранный track_id (если есть).
    """
    track_id = auto_ptz_manager.get_target(camera_id)
    return {"status": "ok", "camera_id": camera_id, "track_id": track_id}
