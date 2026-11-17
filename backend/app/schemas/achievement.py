import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.player import PlayerBrief

ConditionType = Literal[
    "sessions_completed", "score_reached", "total_play_seconds", "wins", "leaderboard_rank"
]
KEY_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")


class AchievementCreate(BaseModel):
    key: str = Field(description="Stable identifier, lowercase letters, digits and underscores")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    condition_type: ConditionType
    threshold: int = Field(ge=1, le=2_000_000_000)
    icon: str = Field(default="trophy", min_length=1, max_length=32)
    is_enabled: bool = True

    @field_validator("key")
    @classmethod
    def _valid_key(cls, value: str) -> str:
        if not KEY_PATTERN.match(value):
            raise ValueError("key must match [a-z0-9_]{1,64}")
        return value


class AchievementUpdate(BaseModel):
    """Editable fields. `key` and `condition_type` are fixed after creation."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    threshold: int | None = Field(default=None, ge=1, le=2_000_000_000)
    icon: str | None = Field(default=None, min_length=1, max_length=32)
    is_enabled: bool | None = None


class AchievementBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    icon: str


class AchievementOut(AchievementBrief):
    description: str
    condition_type: ConditionType
    threshold: int
    is_enabled: bool
    created_at: datetime
    unlock_count: int = 0
    unlock_rate: float = Field(
        default=0.0, description="Share of the game's players who unlocked it"
    )


class UnlockOut(BaseModel):
    id: uuid.UUID
    unlocked_at: datetime
    session_id: uuid.UUID | None
    achievement: AchievementBrief
    player: PlayerBrief
