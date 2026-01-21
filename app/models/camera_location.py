from sqlalchemy import Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .camera import Camera

from .base import Base

class CameraLocation(Base):
    __tablename__ = "camera_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id"), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="location")

    def __repr__(self):
        return f"Location ({self.lat}, {self.lon}, {self.height}, {self.rate})"

    @property
    def camera_name(self) -> str:
        return self.camera.name