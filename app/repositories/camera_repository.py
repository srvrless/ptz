from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select

from app.models.camera import Camera
from app.models.camera_connection import CameraConnection
from app.models.camera_location import CameraLocation
from app.models.camera_ptz import CameraPTZ
from app.models.ptz_types import PTZType
from app.config.settings import CameraConfig
from app.db.session import Session as DBSession
from logger.setup_logger import get_logger

logger = get_logger("camera_repository")


class CameraRepository:
    """
    Репозиторий для работы с камерами в БД
    Преобразует SQLAlchemy модели в Pydantic CameraConfig для совместимости с существующим кодом
    """

    def __init__(self, session: Session):
        self.session = session

    def _db_to_config(self, camera: Camera) -> CameraConfig:
        """
        Преобразует SQLAlchemy модель Camera в Pydantic CameraConfig
        """
        if not camera.connection:
            raise ValueError(f"Camera {camera.id} has no connection data")
        if not camera.location:
            raise ValueError(f"Camera {camera.id} has no location data")
        if not camera.ptz or not camera.ptz.ptz_type:
            raise ValueError(f"Camera {camera.id} has no PTZ type")

        return CameraConfig(
            id=camera.id,
            name=camera.name,
            host=camera.connection.host,
            user=camera.connection.username,
            password=camera.connection.password,
            port=camera.connection.port,
            rtsp_url=camera.connection.rtsp_url,
            lat=camera.location.lat,
            lon=camera.location.lon,
            height=camera.location.height,
            rate=camera.location.rate,
            ptz_type=camera.ptz.ptz_type.type,
        )

    def get_all_cameras(self, enabled_only: bool = True) -> Dict[int, CameraConfig]:
        """
        Получить все камеры из БД.
        """
        query = select(Camera).options(
            joinedload(Camera.connection),
            joinedload(Camera.location),
            joinedload(Camera.ptz).joinedload(CameraPTZ.ptz_type),
        )
        
        if enabled_only:
            query = query.where(Camera.enabled == True)
        
        cameras = self.session.scalars(query).unique().all()
        
        result = {}
        for camera in cameras:
            try:
                config = self._db_to_config(camera)
                result[config.id] = config
            except ValueError as e:
                logger.warning(f"Skipping camera {camera.id}: {e}")
                continue
        
        return result

    def get_camera_by_id(self, camera_id: int) -> Optional[CameraConfig]:
        """
        Получить камеру по ID.
        """
        try:
            camera_db_id = int(str(camera_id).replace("camera", ""))
        except ValueError:
            # Если camera_id не число, пробуем найти по name
            query = select(Camera).where(Camera.name == camera_id).options(
                joinedload(Camera.connection),
                joinedload(Camera.location),
                joinedload(Camera.ptz).joinedload(CameraPTZ.ptz_type),
            )
            camera = self.session.scalar(query)
        else:
            query = select(Camera).where(Camera.id == camera_db_id).options(
                joinedload(Camera.connection),
                joinedload(Camera.location),
                joinedload(Camera.ptz).joinedload(CameraPTZ.ptz_type),
            )
            camera = self.session.scalar(query)
        
        if not camera or not camera.enabled:
            return None
        
        try:
            return self._db_to_config(camera)
        except ValueError as e:
            logger.error(f"Error converting camera {camera_id} to config: {e}")
            return None

    def create_camera(
        self,
        name: str,
        host: str,
        username: str,
        password: str,
        port: int,
        rtsp_url: str,
        rtsp_url_ik: str,
        lat: float,
        lon: float,
        height: float,
        rate: float,
        ptz_type: str,
        enabled: bool = True,
    ) -> CameraConfig:
        """
        Создать новую камеру в БД.
        
        Returns:
            CameraConfig созданной камеры
        """
        # Проверяем, существует ли PTZ тип
        ptz_type_obj = self.session.scalar(
            select(PTZType).where(PTZType.type == ptz_type.lower())
        )
        if not ptz_type_obj:
            raise ValueError(f"PTZ type '{ptz_type}' not found. Available types: onvif, tms20")

        # Создаём камеру
        camera = Camera(
            name=name,
            enabled=enabled,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(camera)
        self.session.flush()  # Получаем ID камеры

        # Создаём связанные данные
        camera.connection = CameraConnection(
            camera_id=camera.id,
            host=host,
            port=port,
            rtsp_url=rtsp_url,
            rtsp_url_ik=rtsp_url_ik,
            username=username,
            password=password,
        )

        camera.location = CameraLocation(
            camera_id=camera.id,
            lat=lat,
            lon=lon,
            height=height,
            rate=rate,
        )

        camera.ptz = CameraPTZ(
            camera_id=camera.id,
            type_id=ptz_type_obj.id,
        )

        self.session.commit()
        logger.info(f"Created camera {camera.id} ({name})")
        
        return self._db_to_config(camera)

    def update_camera(
        self,
        camera_id: int,
        name: Optional[str] = None,
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        port: Optional[int] = None,
        rtsp_url: Optional[str] = None,
        rtsp_url_ik: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        height: Optional[float] = None,
        rate: Optional[float] = None,
        ptz_type: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[CameraConfig]:
        """
        Обновить данные камеры.
        
        Returns:
            CameraConfig обновлённой камеры или None, если камера не найдена
        """
        try:
            camera_db_id = int(str(camera_id).replace("camera", ""))
        except ValueError:
            camera = self.session.scalar(
                select(Camera).where(Camera.name == camera_id)
            )
        else:
            camera = self.session.get(Camera, camera_db_id)
        
        if not camera:
            return None

        # Обновляем основные поля камеры
        if name is not None:
            camera.name = name
        if enabled is not None:
            camera.enabled = enabled
        camera.updated_at = datetime.utcnow()

        # Обновляем connection, если нужно
        if camera.connection:
            if host is not None:
                camera.connection.host = host
            if username is not None:
                camera.connection.username = username
            if password is not None:
                camera.connection.password = password
            if port is not None:
                camera.connection.port = port
            if rtsp_url is not None:
                camera.connection.rtsp_url = rtsp_url
            if rtsp_url_ik is not None:
                camera.connection.rtsp_url_ik = rtsp_url_ik
        else:
            # Если connection нет, создаём его
            if any([host, username, password, port, rtsp_url, rtsp_url_ik]):
                camera.connection = CameraConnection(
                    camera_id=camera.id,
                    host=host or "",
                    username=username or "",
                    password=password or "",
                    port=port or 554,
                    rtsp_url=rtsp_url or "",
                    rtsp_url_ik=rtsp_url_ik or "",
                )

        # Обновляем location, если нужно
        if camera.location:
            if lat is not None:
                camera.location.lat = lat
            if lon is not None:
                camera.location.lon = lon
            if height is not None:
                camera.location.height = height
            if rate is not None:
                camera.location.rate = rate
        else:
            # Если location нет, создаём его
            if any([lat is not None, lon is not None, height is not None, rate is not None]):
                camera.location = CameraLocation(
                    camera_id=camera.id,
                    lat=lat or 0.0,
                    lon=lon or 0.0,
                    height=height or 0.0,
                    rate=rate or 0.0,
                )

        # Обновляем PTZ тип, если нужно
        if ptz_type is not None:
            ptz_type_obj = self.session.scalar(
                select(PTZType).where(PTZType.type == ptz_type.lower())
            )
            if not ptz_type_obj:
                raise ValueError(f"PTZ type '{ptz_type}' not found")
            
            if camera.ptz:
                camera.ptz.type_id = ptz_type_obj.id
            else:
                camera.ptz = CameraPTZ(
                    camera_id=camera.id,
                    type_id=ptz_type_obj.id,
                )

        self.session.commit()
        logger.info(f"Updated camera {camera.id}")
        
        return self._db_to_config(camera)

    def delete_camera(self, camera_id: str, soft_delete: bool = True) -> bool:
        """
        Удалить камеру.
        
        Args:
            camera_id: ID камеры
            soft_delete: Если True, просто отключает камеру (enabled=False), иначе удаляет физически
            
        Returns:
            True, если камера удалена, False если не найдена
        """
        try:
            camera_db_id = int(str(camera_id).replace("camera", ""))
        except ValueError:
            camera = self.session.scalar(
                select(Camera).where(Camera.name == camera_id)
            )
        else:
            camera = self.session.get(Camera, camera_db_id)
        
        if not camera:
            return False

        if soft_delete:
            camera.enabled = False
            camera.updated_at = datetime.utcnow()
            logger.info(f"Soft deleted camera {camera.id}")
        else:
            self.session.delete(camera)
            logger.info(f"Hard deleted camera {camera.id}")
        
        self.session.commit()
        return True


def get_camera_repository(session: Optional[Session] = None) -> CameraRepository:
    """
    Создаёт экземпляр CameraRepository
    """
    if session is None:
        session = DBSession()
    return CameraRepository(session)

