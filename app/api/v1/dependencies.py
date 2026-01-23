from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import config
from app.services import (
    CameraService,
    PTZService,
    camera_service_instance,
    ptz_service_instance,
)
from app.utils.uow import InterfaceUnitOfWork, UnitOfWork

security = HTTPBearer()


def get_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    if token != config.app_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return token


def get_camera_service() -> CameraService:
    # Можно вернуть singleton, как сейчас
    return camera_service_instance


def get_ptz_service() -> PTZService:
    return ptz_service_instance


UOWDep = Annotated[InterfaceUnitOfWork, Depends(UnitOfWork)]
