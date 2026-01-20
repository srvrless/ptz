from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

class PTZType(Base):
    __tablename__ = "ptz_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return self.type