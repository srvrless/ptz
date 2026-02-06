from pydantic import BaseModel
from app.config.settings import DetectorMode

class DetectorModeRequest(BaseModel):
    """Запрос на переключение режима детектора."""

    mode: DetectorMode


class DetectorModeResponse(BaseModel):
    """Ответ с текущим режимом детектора."""

    current_mode: str
    message: str


class DetectorStatusResponse(BaseModel):
    """Полный статус детектора."""

    current_mode: str | None
    available_modes: dict
