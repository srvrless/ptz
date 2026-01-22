from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    def from_camera(cls, camera) -> "CameraResponse":
        """
        Создаёт DTO из SQLAlchemy модели Camera.
        Должна вызываться ВНУТРИ активной сессии.
        """
        return cls.model_validate(camera)


class CreateCamera(BaseModel):
    name: str
    host: str
    username: str
    password: str
    port: int
    rtsp_url: str
    rtsp_url_ik: str
    lat: float
    lon: float
    height: float
    rate: float
    ptz_type: str
    enabled: bool = True

    model_config = ConfigDict(from_attributes=True)

    def dict_for_repo(self) -> dict:
        """Возвращает параметры для передачи в репозиторий"""
        return {
            "name": self.name,
            "host": self.host,
            "username": self.username,
            "password": self.password,
            "port": self.port,
            "rtsp_url": self.rtsp_url,
            "rtsp_url_ik": self.rtsp_url_ik,
            "lat": self.lat,
            "lon": self.lon,
            "height": self.height,
            "rate": self.rate,
            "ptz_type": self.ptz_type,
            "enabled": self.enabled,
        }


class CreateCameraResponse(CreateCamera):
    id: int

    @classmethod
    def from_camera(cls, camera) -> "CreateCameraResponse":
        """
        Создаёт DTO из SQLAlchemy модели Camera.
        Должна вызываться ВНУТРИ активной сессии.
        """
        return cls(
            id=camera.id,
            name=camera.name,
            host=camera.connection.host,
            username=camera.connection.username,
            password=camera.connection.password,
            port=camera.connection.port,
            rtsp_url=camera.connection.rtsp_url,
            rtsp_url_ik=camera.connection.rtsp_url_ik,
            lat=camera.location.lat,
            lon=camera.location.lon,
            height=camera.location.height,
            rate=camera.location.rate,
            ptz_type=camera.ptz.ptz_type.type,
            enabled=camera.enabled,
        )

    model_config = ConfigDict(from_attributes=True)


class UpdateCamera(BaseModel):
    name: str | None
    host: str | None
    username: str | None
    password: str | None
    port: int | None
    rtsp_url: str | None
    rtsp_url_ik: str | None
    lat: float | None
    lon: float | None
    height: float | None
    rate: float | None
    ptz_type: str | None
    enabled: bool | None = True

    def dict_for_repo(self) -> dict:
        """Возвращает только не-None параметры для передачи в репозиторий"""
        return self.model_dump(exclude_none=True)


class UpdateCameraResponse(UpdateCamera):
    id: int
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_camera(cls, camera) -> "UpdateCameraResponse":
        """
        Создаёт DTO из SQLAlchemy модели Camera.
        Должна вызываться ВНУТРИ активной сессии.
        """
        return cls(
            id=camera.id,
            name=camera.name,
            host=camera.connection.host,
            username=camera.connection.username,
            password=camera.connection.password,
            port=camera.connection.port,
            rtsp_url=camera.connection.rtsp_url,
            rtsp_url_ik=camera.connection.rtsp_url_ik,
            lat=camera.location.lat,
            lon=camera.location.lon,
            height=camera.location.height,
            rate=camera.location.rate,
            ptz_type=camera.ptz.ptz_type.type,
            enabled=camera.enabled,
        )

    model_config = ConfigDict(from_attributes=True)
