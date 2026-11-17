import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_METADATA_BYTES = 4096


class PlayerCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=128, description="Your game's player id")
    username: str | None = Field(default=None, min_length=1, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _limit_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value)) > MAX_METADATA_BYTES:
            raise ValueError(f"metadata must be at most {MAX_METADATA_BYTES} bytes of JSON")
        return value


class PlayerStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_sessions: int = 0
    completed_sessions: int = 0
    total_score: int = 0
    best_score: int = 0
    wins: int = 0
    total_play_seconds: int = 0
    achievements_count: int = 0


class PlayerBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str
    username: str


class PlayerOut(PlayerBrief):
    metadata: dict[str, Any] = Field(validation_alias="meta")
    is_simulated: bool
    created_at: datetime
    last_active_at: datetime
    stats: PlayerStatsOut = Field(default_factory=PlayerStatsOut)

    @field_validator("stats", mode="before")
    @classmethod
    def _default_stats(cls, value: Any) -> Any:
        return value if value is not None else {}
