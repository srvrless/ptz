from typing import Annotated

from app.utils.uow import InterfaceUnitOfWork, UnitOfWork
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config.settings import config
from app.services import camera_service, ptz_service
from app.services import CameraService, PTZService

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
    return camera_service


def get_ptz_service() -> PTZService:
    return ptz_service

UOWDep = Annotated[InterfaceUnitOfWork, Depends(UnitOfWork)]