import hashlib
import logging
import uuid

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.repositories.leaderboards import LeaderboardRepository
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardPage
from app.schemas.player import PlayerBrief, PlayerStatsOut

logger = logging.getLogger("app.cache")


def _version_key(game_id: uuid.UUID) -> str:
    return f"gp:game:{game_id}:lbv"


async def bump_leaderboard_version(game_id: uuid.UUID) -> None:
    """Invalidate every cached leaderboard page of a game (called whenever ranks may change)."""
    try:
        await get_redis().incr(_version_key(game_id))
    except (RedisError, OSError):
        logger.warning("leaderboard_cache_invalidate_failed")


async def _cache_key(game_id: uuid.UUID, params: tuple) -> str | None:
    try:
        version = await get_redis().get(_version_key(game_id)) or "0"
    except (RedisError, OSError):
        return None
    digest = hashlib.sha256("|".join(map(str, params)).encode()).hexdigest()[:32]
    return f"gp:game:{game_id}:lb:{version}:{digest}"


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
    """Ranked page, cached in Redis. The cache key embeds a per-game version number, so a
    bump makes all old entries unreachable; the TTL is only a safety net."""
    params = (metric, period, q, min_value, player_id, order, limit, offset)
    cache_key = await _cache_key(game_id, params)
    if cache_key:
        try:
            cached = await get_redis().get(cache_key)
            if cached:
                return LeaderboardPage.model_validate_json(cached)
        except (RedisError, OSError, ValueError):
            logger.warning("leaderboard_cache_read_failed")

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
    page = LeaderboardPage(
        items=[
            LeaderboardEntry(
                rank=rank,
                value=value,
                player=PlayerBrief.model_validate(player),
                stats=PlayerStatsOut.model_validate(player.stats or {}),
            )
            for rank, value, player in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
        metric=metric,
        period=period,
    )
    if cache_key:
        try:
            await get_redis().set(
                cache_key,
                page.model_dump_json(),
                ex=get_settings().leaderboard_cache_ttl_seconds,
            )
        except (RedisError, OSError):
            logger.warning("leaderboard_cache_write_failed")
    return page
