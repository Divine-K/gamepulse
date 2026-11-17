import json
import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.player import PlayerBrief

CUSTOM_EVENT_PATTERN = re.compile(r"^custom_[a-z0-9_]{1,56}$")
MAX_PAYLOAD_BYTES = 8192


class LevelUpPayload(BaseModel):
    """Validated payload for `player_level_up`."""

    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=1, le=100_000)
    previous_level: int | None = Field(default=None, ge=0, le=100_000)


# Externally submittable event types with a validated schema. `custom_*` types are free-form.
KNOWN_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {"player_level_up": LevelUpPayload}


class EventCreate(BaseModel):
    event_type: str = Field(
        min_length=1,
        max_length=64,
        description="`player_level_up` or any `custom_<name>` (lowercase letters, digits, _)",
    )
    player_external_id: str | None = Field(default=None, min_length=1, max_length=128)
    session_id: uuid.UUID | None = None
    occurred_at: datetime | None = Field(
        default=None, description="When it happened (UTC). Defaults to now; max 7 days old."
    )
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def _limit_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value)) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"payload must be at most {MAX_PAYLOAD_BYTES} bytes of JSON")
        return value


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    player_id: uuid.UUID | None
    session_id: uuid.UUID | None
    occurred_at: datetime
    received_at: datetime
    payload: dict[str, Any]
    is_simulated: bool


class EventWithPlayer(EventOut):
    player: PlayerBrief | None = None
