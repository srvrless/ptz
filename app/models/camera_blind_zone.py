from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .camera import Camera


class CameraBlindZone(Base):
    __tablename__ = "camera_blind_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id"),
        nullable=False,
    )
    sector_min_m: Mapped[float] = mapped_column(Float, nullable=False)
    sector_max_m: Mapped[float] = mapped_column(Float, nullable=False)
    az_start_deg: Mapped[float] = mapped_column(Float, nullable=False)
    az_end_deg: Mapped[float] = mapped_column(Float, nullable=False)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="blind_zones")

    def __repr__(self) -> str:
        return (
            f"BlindZone(camera_id={self.camera_id}, "
            f"sector=({self.sector_min_m}, {self.sector_max_m}), "
            f"az=({self.az_start_deg}, {self.az_end_deg}))"
        )
