import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.leaderboards import LeaderboardRepository
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardPage
from app.schemas.player import PlayerBrief, PlayerStatsOut


async def build_leaderboard(
    session: AsyncSession,
    game_id: uuid.UUID,
    metric: str,
    *,
    period: str,
    q: str | None,
    min_value: int | None,
    player_id: uuid.UUID | None,
    order: str,
    limit: int,
    offset: int,
) -> LeaderboardPage:
    rows, total = await LeaderboardRepository(session).page(
        game_id,
        metric,
        period=period,
        q=q,
        min_value=min_value,
        player_id=player_id,
        order=order,
        limit=limit,
        offset=offset,
    )
    entries = [
        LeaderboardEntry(
            rank=rank,
            value=value,
            player=PlayerBrief.model_validate(player),
            stats=PlayerStatsOut.model_validate(player.stats or {}),
        )
        for rank, value, player in rows
    ]
    return LeaderboardPage(
        items=entries, total=total, limit=limit, offset=offset, metric=metric, period=period
    )
