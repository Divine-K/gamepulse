import uuid

from pydantic import BaseModel, Field

from app.schemas.event import EventCreate


class SimPlayerCreate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)


class SimSessionStart(BaseModel):
    player_id: uuid.UUID


class SimScore(BaseModel):
    value: int = Field(ge=0, le=2_000_000_000)


class SimEnd(BaseModel):
    score: int | None = Field(default=None, ge=0, le=2_000_000_000)
    result: str | None = Field(default=None, pattern="^(win|loss|draw)$")


class SimEvent(BaseModel):
    """A custom event sent as a simulated player (or with no player at all)."""

    event_type: str = Field(min_length=1, max_length=64)
    player_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    payload: dict = Field(default_factory=dict)

    def to_create(self, player_external_id: str | None) -> EventCreate:
        return EventCreate(
            event_type=self.event_type,
            player_external_id=player_external_id,
            session_id=self.session_id,
            payload=self.payload,
        )


class SimAward(BaseModel):
    achievement_id: uuid.UUID


class SimAwardResult(BaseModel):
    awarded: bool
    achievement_key: str


class SimSummary(BaseModel):
    players: int
    sessions: int
    events: int


class SimCleared(BaseModel):
    deleted: SimSummary
