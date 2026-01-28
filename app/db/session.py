from sqlalchemy.orm import sessionmaker

from app.db.base import engine

Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
