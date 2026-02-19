from fastapi import APIRouter
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaSyncRoute

from app.config.settings import CameraConfig
from app.core.ptz.manager import PTZCameraManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.schemas.auto_ptz import TrackRequest
from app.utils.uow import InterfaceUnitOfWork

router = APIRouter(prefix="/api", tags=["auto-ptz"], route_class=DishkaSyncRoute)


def _get_camera_config(uow: InterfaceUnitOfWork, camera_id: int) -> CameraConfig:
    """Конфиг из БД."""
    with uow:
        camera = uow.camera.get_camera_by_id(camera_id)
        if camera is None:
            from app.exceptions import CameraNotFoundError

            raise CameraNotFoundError(camera_id)
        return CameraConfig.from_db_model(camera)


def _resolve_camera_config(
    ptz_manager: PTZCameraManager,
    uow: InterfaceUnitOfWork,
    camera_id: int,
) -> CameraConfig:
    """Из кэша, если камера инициализирована; иначе запрос в БД."""
    if ptz_manager.is_initialized(camera_id):
        return ptz_manager.get_cached_config(camera_id)
    return _get_camera_config(uow, camera_id)


@router.post("/track/{camera_id}")
def start_auto_tracking(
    camera_id: int,
    body: TrackRequest,
    auto_ptz_manager: FromDishka[AutoPTZManager],
    ptz_manager: FromDishka[PTZCameraManager],
    uow: FromDishka[InterfaceUnitOfWork],
):
    """Включить слежение за объектом с указанным track_id."""
    cam_cfg = _resolve_camera_config(ptz_manager, uow, camera_id)
    auto_ptz_manager.set_target(camera_id, body.track_id, cam_cfg)
    return {"status": "ok", "camera_id": camera_id, "track_id": body.track_id}


@router.post("/stop/{camera_id}")
def stop_auto_tracking(
    camera_id: int,
    auto_ptz_manager: FromDishka[AutoPTZManager],
    ptz_manager: FromDishka[PTZCameraManager],
    uow: FromDishka[InterfaceUnitOfWork],
):
    """Выключить автослежение для камеры."""
    cam_cfg = _resolve_camera_config(ptz_manager, uow, camera_id)
    auto_ptz_manager.clear_target(camera_id, cam_cfg)
    return {"status": "ok", "camera_id": camera_id}


@router.get("/status/{camera_id}")
def get_auto_tracking_status(
    camera_id: int,
    auto_ptz_manager: FromDishka[AutoPTZManager],
    ptz_manager: FromDishka[PTZCameraManager],
    uow: FromDishka[InterfaceUnitOfWork],
):
    """Получить текущий выбранный track_id (если есть)."""
    cam_cfg = _resolve_camera_config(ptz_manager, uow, camera_id)
    track_id = auto_ptz_manager.get_target(camera_id, cam_cfg)
    return {"status": "ok", "camera_id": camera_id, "track_id": track_id}
