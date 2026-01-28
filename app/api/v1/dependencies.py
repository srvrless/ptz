from typing import Annotated

from fastapi import Depends

from app.services import (
    CameraService,
    PTZService,
)
from app.utils.uow import InterfaceUnitOfWork, UnitOfWork

from app.config.settings import get_config
from app.core.camera.manager import camera_manager
from app.core.ptz.manager import ptz_camera_manager



def get_camera_service() -> CameraService:
    return CameraService(
        camera_manager=camera_manager,
        config=get_config(),
    )
def get_ptz_service() -> PTZService:
    return PTZService(
        ptz_manager=ptz_camera_manager,
        config=get_config(),
    )

UOWDep = Annotated[InterfaceUnitOfWork, Depends(UnitOfWork)]
