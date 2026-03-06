from fastapi import APIRouter
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaSyncRoute

from app.schemas.camera import CameraResponse
from app.schemas.ptz import (
    ContinuousMoveRequest,
    MoveExcludedCameras,
    MoveRequest,
    ZoomRequest,
)
from app.services import PTZService

router = APIRouter(prefix="/api", tags=["ptz"], route_class=DishkaSyncRoute)


# ---------- MOVE ----------


@router.post("/ptz/{camera_id}/move/")
def ptz_move(
    camera_id: int,
    body: MoveRequest,
    # _token: str = Depends(get_token),
    ptz_service: FromDishka[PTZService],
):
    """
    Абсолютное позиционирование PTZ-камеры по координатам цели.

    Ожидает JSON:
    {
      "lat": 55.123,
      "lon": 37.123,
      "height": 10.5,
      "zoom": 0.5,      # опционально
      "radar_id": 1     # опционально
    }

    Возвращает:
    { "status": "ok", "azimut": float }
    """
    result = ptz_service.move_to_target(
        camera_id=camera_id,
        lat=body.lat,
        lon=body.lon,
        height=body.height,
        zoom=body.zoom,
        radar_id=body.radar_id,
    )
    return result


@router.post("/ptz/move/")
def ptz_move_to_target(
    body: MoveExcludedCameras,
    ptz_service: FromDishka[PTZService],
) -> CameraResponse:
    """
    Абсолютное позиционирование PTZ-камеры по координатам цели.

    Ожидает JSON:
    {
        "track_id": int
        "lat": float,
        "lon": float,
        "height": float,
        "zoom": float,      # опционально
        "radar_id": int     # опционально
        "excluded_cameras": list[int] # опционально
    }

    Возвращает:
    { "camera": CameraResponse, "azimut": float }
    """
    result = ptz_service.move_to_target_with_excluded_cameras(
        excluded_cameras_id=body.excluded_cameras_id,
        lat=body.lat,
        lon=body.lon,
        height=body.height,
        zoom=body.zoom,
        radar_id=body.radar_id,
    )
    return result


# ---------- CONTINUOUS MOVE ----------


@router.post("/ptz/{camera_id}/continuous_move/")
def ptz_continuous_move(
    camera_id: int,
    body: ContinuousMoveRequest,
    # _token: str = Depends(get_token),
    ptz_service: FromDishka[PTZService],
):
    """
    Непрерывное движение PTZ.

    JSON:
    {
      "x": 0.1,   # скорость pan [-1, 1]
      "y": 0.0,   # скорость tilt [-1, 1]
      "zoom": 0.0 # скорость zoom [-1, 1]
    }

    Возвращает:
    { "status": "ok" }
    """
    ptz_service.continuous_move(
        camera_id=camera_id,
        x=body.x,
        y=body.y,
        zoom=body.zoom,
    )
    return {"status": "ok"}


# ---------- STOP ----------


@router.post("/ptz/{camera_id}/stop/")
def ptz_stop(
    camera_id: int,
    ptz_service: FromDishka[PTZService],
):
    """
    Остановить PTZ-движение.

    Возвращает:
    { "status": "ok", "azimut": float | null }
    """
    result = ptz_service.stop(camera_id)
    return result


# ---------- ZOOM ----------


@router.post("/ptz/{camera_id}/zoom/")
def ptz_zoom(
    camera_id: int,
    body: ZoomRequest,
    ptz_service: FromDishka[PTZService],
):
    """
    Управление зумом PTZ.

    JSON:
    {
      "zoom": 0.1  # изменение зума (может быть отрицательным)
    }

    Возвращает:
    { "status": "ok" }
    """
    ptz_service.set_zoom(camera_id, zoom_delta=body.zoom)
    return {"status": "ok"}
