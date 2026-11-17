import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.achievement import AchievementBrief
from app.schemas.player import PlayerBrief

SessionStatus = Literal["active", "completed", "abandoned"]
SessionResult = Literal["win", "loss", "draw"]


class SessionStart(BaseModel):
    player_external_id: str = Field(min_length=1, max_length=128)


class SessionEnd(BaseModel):
    score: int | None = Field(
        default=None,
        ge=0,
        le=2_000_000_000,
        description="Final score. Defaults to the live score sent via /scores (or 0).",
    )
    result: SessionResult | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: SessionStatus
    result: SessionResult | None
    score: int
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    last_heartbeat_at: datetime
    is_simulated: bool
    player: PlayerBrief


class SessionEndOut(SessionOut):
    unlocked_achievements: list[AchievementBrief] = Field(
        default_factory=list, description="Achievements newly awarded by this call"
    )
