from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .camera_connection import CameraConnection
    from .camera_location import CameraLocation
    from .camera_ptz import CameraPTZ


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    connection: Mapped[Optional["CameraConnection"]] = relationship(
        "CameraConnection",
        back_populates="camera",
        uselist=False,
        cascade="all, delete-orphan",
    )
    location: Mapped[Optional["CameraLocation"]] = relationship(
        "CameraLocation",
        back_populates="camera",
        uselist=False,
        cascade="all, delete-orphan",
    )
    ptz: Mapped[Optional["CameraPTZ"]] = relationship(
        "CameraPTZ",
        back_populates="camera",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return self.name

    @property
    def location_lat(self) -> float:
        return self.location.lat

    @property
    def location_lon(self) -> float:
        return self.location.lon

    @property
    def location_height(self) -> float:
        return self.location.height

    @property
    def location_rate(self) -> float:
        return self.location.rate

    @property
    def ptz_type(self) -> str:
        return self.ptz.ptz_type
