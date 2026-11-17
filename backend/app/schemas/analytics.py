from datetime import date

from pydantic import BaseModel, Field


class WindowStats(BaseModel):
    new_players: int
    sessions: int
    active_players: int
    events: int
    avg_session_duration_seconds: float | None


class OverviewOut(BaseModel):
    # All-time totals
    total_players: int
    total_sessions: int
    completed_sessions: int
    total_events: int
    avg_session_duration_seconds: float | None
    # Rolling activity windows
    daily_active_players: int = Field(description="Distinct players with activity in the last 24h")
    monthly_active_players: int = Field(
        description="Distinct players with activity in the last 30d"
    )
    currently_active_players: int
    currently_active_source: str
    # The selected period and the period just before it, for trend comparison
    period_days: int
    current: WindowStats
    previous: WindowStats
    include_simulated: bool


class EngagementPoint(BaseModel):
    date: date
    active_players: int
    new_players: int
    sessions_started: int
    sessions_completed: int
    avg_session_duration_seconds: float | None
    events: int


class EngagementOut(BaseModel):
    days: int
    points: list[EngagementPoint]
    include_simulated: bool


class RetentionPoint(BaseModel):
    day: int = Field(description="Days after registration")
    eligible_players: int = Field(description="Players registered at least `day` days ago")
    retained_players: int = Field(description="Of those, players active exactly `day` days later")
    rate: float | None = Field(description="retained / eligible, or null with no eligible players")


class RetentionOut(BaseModel):
    points: list[RetentionPoint]
    include_simulated: bool


class ScoreBucket(BaseModel):
    start: int
    end: int
    count: int


class ScoreDistributionOut(BaseModel):
    completed_sessions: int
    average: float | None
    median: float | None
    p90: float | None
    min: int | None
    max: int | None
    buckets: list[ScoreBucket]
    include_simulated: bool


class AchievementStat(BaseModel):
    key: str
    name: str
    icon: str
    is_enabled: bool
    unlock_count: int
    unlock_rate: float


class UnlockDay(BaseModel):
    date: date
    count: int


class AchievementAnalyticsOut(BaseModel):
    total_unlocks: int
    achievements: list[AchievementStat]
    unlocks_by_day: list[UnlockDay]
    days: int
    include_simulated: bool
