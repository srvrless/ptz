from sqlalchemy import Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

from .camera import Camera
from .ptz_types import PTZType
from .base import Base

class CameraPTZ(Base):
    __tablename__ = "camera_ptz"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id"), nullable=False)
    type_id: Mapped[int] = mapped_column(Integer, ForeignKey("ptz_types.id"), nullable=False)