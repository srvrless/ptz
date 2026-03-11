from fastapi import APIRouter
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaSyncRoute

from app.models.camera import Camera
from app.schemas.camera import CameraResponse
from app.utils.uow import InterfaceUnitOfWork

router = APIRouter(prefix="/api", tags=["cameras"], route_class=DishkaSyncRoute)


@router.get("/cameras")
def list_cameras(uow: FromDishka[InterfaceUnitOfWork]) -> list[CameraResponse]:
    with uow:
        cameras = uow.session.query(Camera).all()
        return [CameraResponse.from_camera(c) for c in cameras]


@router.get("/cameras/{camera_id}")
def one_camera(
    camera_id: int, uow: FromDishka[InterfaceUnitOfWork]
) -> CameraResponse:
    with uow:
        camera = uow.session.query(Camera).filter(Camera.id == camera_id).one_or_none()
        if camera is None or not camera.enabled:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Camera not found or not enabled")
        return CameraResponse.from_camera(camera)

