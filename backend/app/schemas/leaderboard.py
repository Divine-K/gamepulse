import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Page
from app.schemas.player import PlayerBrief, PlayerStatsOut

SCORE_CATEGORY_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")


class LeaderboardEntry(BaseModel):
    rank: int = Field(description="Competition ranking: ties share a rank")
    value: int
    player: PlayerBrief
    stats: PlayerStatsOut


class LeaderboardPage(Page[LeaderboardEntry]):
    metric: str
    period: str


class ScoreSubmit(BaseModel):
    player_external_id: str = Field(min_length=1, max_length=128)
    value: int = Field(ge=0, le=2_000_000_000)
    category: str = Field(default="score", min_length=1, max_length=64)
    session_id: uuid.UUID | None = Field(
        default=None,
        description="Attach to an active session; for category 'score' it becomes the live score",
    )


class ScoreOut(BaseModel):
    id: uuid.UUID
    category: str
    value: int
    session_id: uuid.UUID | None
    created_at: datetime


Period = Literal["all", "daily", "weekly", "monthly"]
Order = Literal["desc", "asc"]
