from pydantic import BaseModel, Field, field_validator


class MoveRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Широта цели")
    lon: float = Field(..., ge=-180, le=180, description="Долгота цели")
    height: float = Field(..., description="Высота цели (м, относительно земли)")
    zoom: float = Field(0.0, description="Уровень зума (0..1), опционально")
    radar_id: int = Field(1, description="ID радара (1..N)")

    @field_validator("radar_id")
    @classmethod
    def radar_id_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("radar_id must be >= 1")
        return v


class ContinuousMoveRequest(BaseModel):
    x: float = Field(0.0, ge=-1, le=1, description="Скорость по pan [-1, 1]")
    y: float = Field(0.0, ge=-1, le=1, description="Скорость по tilt [-1, 1]")
    zoom: float = Field(0.0, ge=-1, le=1, description="Скорость по zoom [-1, 1]")


class ZoomRequest(BaseModel):
    zoom: float = Field(..., ge=-1, le=1, description="Изменение зума (может быть отрицательным)")

class TrackRequest(BaseModel):
    track_id: int = Field(..., description="ID объекта для слежения")