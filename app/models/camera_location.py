from sqlalchemy import Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

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