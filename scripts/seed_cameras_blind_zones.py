import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.base import create_db_and_tables
from app.db.session import Session
from app.models.ptz_types import PTZType
from app.models.camera_blind_zone import CameraBlindZone
from app.repositories.camera_repository import CameraRepository


def get_or_create_ptz_type(session, type_name: str) -> PTZType:
    type_name = type_name.lower()
    ptz_type = session.query(PTZType).filter(PTZType.type == type_name).first()
    if ptz_type is None:
        ptz_type = PTZType(type=type_name)
        session.add(ptz_type)
        session.flush()
    return ptz_type


def seed():
    # Создаём таблицы, если их ещё нет
    create_db_and_tables()

    session = Session()
    repo = CameraRepository(session)

    try:
        # Обеспечиваем наличие базового PTZ-типа
        get_or_create_ptz_type(session, "onvif")

        # Простейший набор камер вокруг одной точки
        base_cameras = [
            {
                "name": "cam_north",
                "host": "192.168.0.10",
                "port": 554,
                "rtsp_url": "rtsp://192.168.0.10/stream",
                "rtsp_url_ik": "rtsp://192.168.0.10/ik",
                "username": "admin",
                "password": "admin",
                "lat": 55.7500,
                "lon": 37.6000,
                "height": 10.0,
                "rate": 0.0,  # базовый поворот
                "ptz_type": "onvif",
            },
            {
                "name": "cam_east",
                "host": "192.168.0.11",
                "port": 554,
                "rtsp_url": "rtsp://192.168.0.11/stream",
                "rtsp_url_ik": "rtsp://192.168.0.11/ik",
                "username": "admin",
                "password": "admin",
                "lat": 55.7500,
                "lon": 37.6100,
                "height": 12.0,
                "rate": 0.0,
                "ptz_type": "onvif",
            },
            {
                "name": "cam_south",
                "host": "192.168.0.12",
                "port": 554,
                "rtsp_url": "rtsp://192.168.0.12/stream",
                "rtsp_url_ik": "rtsp://192.168.0.12/ik",
                "username": "admin",
                "password": "admin",
                "lat": 55.7400,
                "lon": 37.6000,
                "height": 8.0,
                "rate": 0.0,
                "ptz_type": "onvif",
            },
        ]

        created_cameras = []

        for cfg in base_cameras:
            cam = repo.create_camera(
                name=cfg["name"],
                host=cfg["host"],
                username=cfg["username"],
                password=cfg["password"],
                port=cfg["port"],
                rtsp_url=cfg["rtsp_url"],
                rtsp_url_ik=cfg["rtsp_url_ik"],
                lat=cfg["lat"],
                lon=cfg["lon"],
                height=cfg["height"],
                rate=cfg["rate"],
                ptz_type=cfg["ptz_type"],
                enabled=True,
            )
            created_cameras.append(cam)

        session.flush()

        # Пример слепых зон для тестов
        # cam_north: "препятствие" в азимутах 234–297° на дальности 10–35 м и 35–70 м
        cam_north = created_cameras[0]
        session.add_all(
            [
                CameraBlindZone(
                    camera_id=cam_north.id,
                    sector_min_m=10.0,
                    sector_max_m=35.0,
                    az_start_deg=234.0,
                    az_end_deg=297.0,
                ),
                CameraBlindZone(
                    camera_id=cam_north.id,
                    sector_min_m=35.0,
                    sector_max_m=70.0,
                    az_start_deg=234.0,
                    az_end_deg=297.0,
                ),
            ]
        )

        # cam_east: слепая зона на востоке (80–100°) ближе 30 м
        cam_east = created_cameras[1]
        session.add(
            CameraBlindZone(
                camera_id=cam_east.id,
                sector_min_m=0.0,
                sector_max_m=30.0,
                az_start_deg=80.0,
                az_end_deg=100.0,
            )
        )

        # cam_south: слепая зона через 0° (350–20°) на дальности 15–60 м
        cam_south = created_cameras[2]
        session.add(
            CameraBlindZone(
                camera_id=cam_south.id,
                sector_min_m=15.0,
                sector_max_m=60.0,
                az_start_deg=350.0,
                az_end_deg=20.0,
            )
        )

        session.commit()
        print("✅ Seed: создано камер:", len(created_cameras))
    except Exception as exc:
        session.rollback()
        print("❌ Seed failed:", exc)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
