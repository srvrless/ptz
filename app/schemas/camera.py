from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class ConnectionResponse(BaseModel):
    """DTO для данных подключения камеры"""
    rtsp_url: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LocationResponse(BaseModel):
    """DTO для геолокации камеры"""
    lat: float
    lon: float
    model_config = ConfigDict(from_attributes=True)


class CameraResponse(BaseModel):
    """DTO для ответа по камере"""
    id: int
    name: str
    connection: Optional[ConnectionResponse] = None
    location: Optional[LocationResponse] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_camera(cls, camera) -> 'CameraResponse':
        """
        Создаёт DTO из SQLAlchemy модели Camera.
        Должна вызываться ВНУТРИ активной сессии.
        """
        return cls.model_validate(camera)