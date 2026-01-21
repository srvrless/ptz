
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.base import create_db_and_tables
from app.db.session import Session
from app.config.settings import AppConfig, _load_cameras_from_settings
from app.models.camera import Camera
from app.models.camera_connection import CameraConnection
from app.models.camera_location import CameraLocation
from app.models.camera_ptz import CameraPTZ
from app.models.ptz_types import PTZType
from logger.setup_logger import get_logger

logger = get_logger("migrate_cameras")


def migrate_cameras_from_env_to_db() -> None:
    """
    Читает конфигурацию камер из .env и записывает в БД.
    """
    logger.info("Creating database tables...")
    create_db_and_tables()

    logger.info("Loading cameras from .env...")
    cfg = AppConfig()
    cameras_from_env = _load_cameras_from_settings(cfg)

    if not cameras_from_env:
        logger.warning("No cameras found in .env (check CAMERAS variable and camera1_*, camera2_*, etc.)")
        return

    logger.info(f"Found {len(cameras_from_env)} cameras in .env")

    db_session = Session()
    try:
        onvif_type = db_session.query(PTZType).filter(PTZType.type == "onvif").first()
        if not onvif_type:
            logger.info("Creating default PTZ types...")
            onvif_type = PTZType(type="onvif")
            tms20_type = PTZType(type="tms20")
            db_session.add_all([onvif_type, tms20_type])
            db_session.commit()
            logger.info("PTZ types created")

        for camera_id, cam_cfg in cameras_from_env.items():
            cam_db_id = camera_id

            existing = db_session.query(Camera).filter(Camera.id == cam_db_id).first()
            if existing:
                logger.info(f"Camera {camera_id} already exists in DB, skipping")
                continue

            logger.info(f"Migrating camera ID={cam_db_id}...")

            camera = Camera(
                id=cam_db_id,
                name=cam_cfg.name or f"Camera {cam_db_id}",
                enabled=True,
            )
            if existing:
                logger.info(f"Camera {camera_id} already exists in DB, skipping")
                continue

            logger.info(f"Migrating camera {camera_id} (ID={cam_db_id})...")

            camera = Camera(
                id=cam_db_id,
                name=cam_cfg.name or camera_id,
                enabled=True,
            )

            connection = CameraConnection(
                camera=camera,
                host=cam_cfg.host,
                port=cam_cfg.port,
                rtsp_url=cam_cfg.rtsp_url,
                rtsp_url_ik=cam_cfg.rtsp_url,  
                username=cam_cfg.user,  
                password=cam_cfg.password,
            )

            location = CameraLocation(
                camera=camera,
                lat=cam_cfg.lat,
                lon=cam_cfg.lon,
                height=cam_cfg.height,
                rate=cam_cfg.rate,
            )

            ptz_type = db_session.query(PTZType).filter(
                PTZType.type == cam_cfg.ptz_type.lower()
            ).first()
            if not ptz_type:
                logger.warning(f"PTZ type '{cam_cfg.ptz_type}' not found, using 'onvif'")
                ptz_type = onvif_type

            ptz = CameraPTZ(
                camera=camera,
                ptz_type=ptz_type,
            )

            db_session.add(camera)
            db_session.add(connection)
            db_session.add(location)
            db_session.add(ptz)
            db_session.flush() 

            logger.info(f"Camera {camera_id} migrated successfully")

        db_session.commit()
        logger.info(f"Migration complete! {len(cameras_from_env)} cameras migrated to DB")

    except Exception as e:
        db_session.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        db_session.close()


if __name__ == "__main__":
    try:
        migrate_cameras_from_env_to_db()
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)
