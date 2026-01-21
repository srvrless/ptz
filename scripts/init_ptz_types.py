"""
Скрипт для инициализации справочника типов PTZ в БД.
Создаёт записи 'onvif' и 'tms20', если их ещё нет.
"""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import Session
from app.models.ptz_types import PTZType
from sqlalchemy import select

def init_ptz_types():
    """Создаёт типы PTZ в БД, если их ещё нет."""
    session = Session()
    
    try:
        # Проверяем, есть ли уже типы
        existing_types = session.scalars(select(PTZType)).all()
        existing_type_names = {ptz.type for ptz in existing_types}
        
        # Типы, которые должны быть
        required_types = ["onvif", "tms20"]
        
        created_count = 0
        for ptz_type_name in required_types:
            if ptz_type_name not in existing_type_names:
                ptz_type = PTZType(type=ptz_type_name)
                session.add(ptz_type)
                created_count += 1
                print(f"Создан тип PTZ: {ptz_type_name}")
            else:
                print(f"ℹТип PTZ уже существует: {ptz_type_name}")
        
        if created_count > 0:
            session.commit()
            print(f"\nСоздано типов PTZ: {created_count}")
        else:
            print("\nВсе типы PTZ уже существуют в БД")
            
    except Exception as e:
        session.rollback()
        print(f"Ошибка при инициализации типов PTZ: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    init_ptz_types()

