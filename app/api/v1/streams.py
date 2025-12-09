from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.v1.deps import get_token, get_camera_service
from app.services import CameraService

router = APIRouter(prefix="/api", tags=["streams"])


@router.get("/stream/{camera_id}/")
def stream_camera(
    camera_id: str,
    #_token: str = Depends(get_token),
    camera_service: CameraService = Depends(get_camera_service),
):
    """
    MJPEG-стрим с камеры.
    Возвращает multipart/x-mixed-replace поток JPEG-кадров.
    """
    gen = camera_service.get_mjpeg_stream(camera_id, enable_detection=True)
    return StreamingResponse(
        gen,
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
