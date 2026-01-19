from abc import ABC, abstractmethod
from typing import Type

from app.db.session import Session
from app.repositories.camera_repository import CameraRepository


class InterfaceUnitOfWork(ABC):
    camera: Type[CameraRepository]

    @abstractmethod
    def __init__(self): ...

    @abstractmethod
    def __enter__(self): ...

    @abstractmethod
    def __exit__(self, *args): ...

    @abstractmethod
    def commit(self): ...

    @abstractmethod
    def rollback(self): ...


class UnitOfWork:
    def __init__(self):
        self.session_factory = Session

    def __enter__(self):
        self.session = self.session_factory()

        self.camera = CameraRepository(self.session)

    def __exit__(self, *args):
        self.rollback()
        self.session.close()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()