from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .camera import Camera
    from .ptz_types import PTZType

from .base import Base

class CameraPTZ(Base):
    __tablename__ = "camera_ptz"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id"), nullable=False)
    type_id: Mapped[int] = mapped_column(Integer, ForeignKey("ptz_types.id"), nullable=False, default=1)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="ptz")
    ptz_type: Mapped["PTZType"] = relationship("PTZType")