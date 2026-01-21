"""
Скрипт для инициализации базы данных.
Создаёт файл БД и все таблицы на основе моделей SQLAlchemy.
"""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.base import create_db_and_tables

if __name__ == "__main__":
    create_db_and_tables()

