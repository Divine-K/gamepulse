"""Dashboard (JWT) analytics. All figures are aggregates over the real database."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import DbSession, OwnedGame
from app.schemas.analytics import (
    AchievementAnalyticsOut,
    EngagementOut,
    OverviewOut,
    RetentionOut,
    ScoreDistributionOut,
)
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/api/v1/games/{game_id}/analytics", tags=["analytics"])

Days = Annotated[int, Query(ge=1, le=365, description="Length of the period in days")]
IncludeSimulated = Annotated[bool, Query(description="Include data created by the event simulator")]


@router.get("/overview", response_model=OverviewOut, summary="Headline metrics and trends")
async def overview(
    game: OwnedGame, db: DbSession, days: Days = 30, include_simulated: IncludeSimulated = True
) -> OverviewOut:
    return await AnalyticsService(db, game.id, include_simulated).overview(days)


@router.get(
    "/engagement",
    response_model=EngagementOut,
    summary="Daily engagement series (UTC days, gaps filled with zeros)",
)
async def engagement(
    game: OwnedGame, db: DbSession, days: Days = 30, include_simulated: IncludeSimulated = True
) -> EngagementOut:
    return await AnalyticsService(db, game.id, include_simulated).engagement(days)


@router.get(
    "/retention",
    response_model=RetentionOut,
    summary="Day-1, day-7 and day-30 retention",
    description=(
        "Of the players who registered at least N days ago, the share who were active exactly "
        "N days after registering. `rate` is null until a player is old enough to be counted."
    ),
)
async def retention(
    game: OwnedGame, db: DbSession, include_simulated: IncludeSimulated = True
) -> RetentionOut:
    return await AnalyticsService(db, game.id, include_simulated).retention()


@router.get("/scores", response_model=ScoreDistributionOut, summary="Score distribution")
async def scores(
    game: OwnedGame,
    db: DbSession,
    buckets: Annotated[int, Query(ge=2, le=30)] = 10,
    include_simulated: IncludeSimulated = True,
) -> ScoreDistributionOut:
    return await AnalyticsService(db, game.id, include_simulated).scores(buckets)


@router.get(
    "/achievements", response_model=AchievementAnalyticsOut, summary="Achievement unlock statistics"
)
async def achievements(
    game: OwnedGame, db: DbSession, days: Days = 30, include_simulated: IncludeSimulated = True
) -> AchievementAnalyticsOut:
    return await AnalyticsService(db, game.id, include_simulated).achievements(days)
