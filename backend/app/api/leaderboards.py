"""Dashboard (JWT) leaderboards. Query parameters are shared with the game API."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DbSession, OwnedGame
from app.schemas.leaderboard import LeaderboardPage, Order, Period
from app.services.leaderboards import build_leaderboard


@dataclass
class LeaderboardQuery:
    """Common query parameters for leaderboard endpoints."""

    period: Annotated[
        Period, Query(description="Time window; only for category:<name> metrics")
    ] = "all"
    q: Annotated[str | None, Query(max_length=100, description="Search username or id")] = None
    min_value: Annotated[int | None, Query(ge=0)] = None
    order: Annotated[Order, Query(description="Display order; ranks are always by value")] = "desc"
    limit: Annotated[int, Query(ge=1, le=100)] = 50
    offset: Annotated[int, Query(ge=0)] = 0


router = APIRouter(prefix="/api/v1/games/{game_id}", tags=["leaderboards"])


@router.get(
    "/leaderboards/{metric}",
    response_model=LeaderboardPage,
    summary="Ranked players for a metric",
    description=(
        "Metrics: `total_score`, `best_score`, `wins`, `achievements`, `completed_sessions`, "
        "or `category:<name>` for any score category submitted via the scores endpoint. "
        "Ties share a rank (1, 2, 2, 4)."
    ),
)
async def leaderboard(
    game: OwnedGame, metric: str, db: DbSession, params: Annotated[LeaderboardQuery, Depends()]
) -> LeaderboardPage:
    return await build_leaderboard(
        db,
        game.id,
        metric,
        period=params.period,
        q=params.q,
        min_value=params.min_value,
        player_id=None,
        order=params.order,
        limit=params.limit,
        offset=params.offset,
    )
