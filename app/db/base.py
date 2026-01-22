import os
from pathlib import Path

from sqlalchemy import create_engine

# Путь к БД: создаём папку db в корне проекта, если её нет
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = PROJECT_ROOT / "db"
DB_DIR.mkdir(exist_ok=True)

DB_URL = f'sqlite:///{DB_DIR / "database.db"}'
engine = create_engine(
    DB_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)


def create_db_and_tables() -> None:
    """
    Создаёт все таблицы в БД
    """
    # Импортируем все модели, чтобы они зарегистрировались в Base.metadata
    from app.models.base import Base
    from app.models.camera import Camera
    from app.models.camera_connection import CameraConnection
    from app.models.camera_location import CameraLocation
    from app.models.camera_ptz import CameraPTZ
    from app.models.ptz_types import PTZType

    # Создаём все таблицы
    Base.metadata.create_all(engine)
    print(f"✅ База данных создана: {DB_URL}")
