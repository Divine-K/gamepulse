"""Active player tracking in Redis.

One sorted set per game: member = player id, score = last heartbeat (epoch seconds). A player
counts as active while their score is within the session timeout. Redis is a cache of the
`game_sessions` table: it is rebuilt from Postgres at startup, and reads fall back to
Postgres if Redis is unavailable.
"""

import logging
import time
import uuid

from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.models import GameSession

logger = logging.getLogger("app.realtime")


def _key(game_id: uuid.UUID | str) -> str:
    return f"gp:game:{game_id}:active"


def _timeout_seconds() -> int:
    return get_settings().session_timeout_minutes * 60


async def touch(game_id: uuid.UUID, player_id: uuid.UUID) -> None:
    try:
        redis = get_redis()
        await redis.zadd(_key(game_id), {str(player_id): time.time()})
        await redis.expire(_key(game_id), _timeout_seconds() * 2)
    except (RedisError, OSError):
        logger.warning("active_tracker_touch_failed")


async def remove(game_id: uuid.UUID, player_id: uuid.UUID) -> None:
    try:
        await get_redis().zrem(_key(game_id), str(player_id))
    except (RedisError, OSError):
        logger.warning("active_tracker_remove_failed")


async def count_from_redis(game_id: uuid.UUID) -> int | None:
    """Active players per Redis, or None if Redis is unavailable."""
    try:
        cutoff = time.time() - _timeout_seconds()
        return int(await get_redis().zcount(_key(game_id), cutoff, "+inf"))
    except (RedisError, OSError):
        return None


async def count_from_postgres(db: AsyncSession, game_id: uuid.UUID) -> int:
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(seconds=_timeout_seconds())
    return (
        await db.scalar(
            select(func.count(func.distinct(GameSession.player_id))).where(
                GameSession.game_id == game_id,
                GameSession.status == "active",
                GameSession.last_heartbeat_at >= cutoff,
            )
        )
        or 0
    )


async def active_players(db: AsyncSession, game_id: uuid.UUID) -> tuple[int, str]:
    """Return (count, source) where source is 'redis' or 'postgres'."""
    from_redis = await count_from_redis(game_id)
    if from_redis is not None:
        return from_redis, "redis"
    return await count_from_postgres(db, game_id), "postgres"


async def rebuild(db: AsyncSession) -> int:
    """Repopulate Redis from active sessions in Postgres (run at startup)."""
    rows = (
        await db.execute(
            select(GameSession.game_id, GameSession.player_id, GameSession.last_heartbeat_at).where(
                GameSession.status == "active"
            )
        )
    ).all()
    try:
        redis = get_redis()
        async with redis.pipeline(transaction=False) as pipe:
            for game_id, player_id, heartbeat in rows:
                pipe.zadd(_key(game_id), {str(player_id): heartbeat.timestamp()})
                pipe.expire(_key(game_id), _timeout_seconds() * 2)
            await pipe.execute()
    except (RedisError, OSError):
        logger.warning("active_tracker_rebuild_failed")
        return 0
    return len(rows)
