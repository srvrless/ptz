from abc import ABC, abstractmethod
from typing import Type

from app.db.session import Session
from app.repositories.camera_repository import CameraRepository


class InterfaceUnitOfWork(ABC):
    camera: CameraRepository

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


class UnitOfWork(InterfaceUnitOfWork):
    def __init__(self):
        self.session_factory =  Session

    def __enter__(self):
        self.session = self.session_factory()
        self.camera = CameraRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
