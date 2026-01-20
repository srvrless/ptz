
from pydantic import BaseModel


class TrackRequest(BaseModel):
    track_id: int
