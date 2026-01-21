from contextlib import contextmanager
from sqlalchemy.orm import scoped_session, sessionmaker
from .base import engine

Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
