import logging
import time

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis import get_redis

logger = logging.getLogger("app.rate_limit")


async def enforce_rate_limit(
    redis: Redis, name: str, identity: str, limit: int, window_seconds: int = 60
) -> None:
    """Fixed-window counter in Redis. Raises 429 when `identity` exceeds `limit` per window.

    Fails open if Redis is unavailable, so an outage doesn't take the API down with it.
    """
    window = int(time.time() // window_seconds)
    key = f"gp:rl:{name}:{identity}:{window}"
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds * 2)
    except RedisError:
        logger.warning("rate_limit_unavailable", extra={"limiter": name})
        return
    if count > limit:
        retry_after = window_seconds - int(time.time() % window_seconds)
        raise AppError(
            "rate_limited",
            "Too many requests. Please slow down.",
            429,
            headers={"Retry-After": str(retry_after)},
        )


class RateLimiter:
    """Per-client-IP limiter, used as a route dependency (login, register).

    Behind a reverse proxy, configure the proxy headers so `request.client` is the real IP.
    """

    def __init__(self, name: str, limit: int | None = None, window_seconds: int = 60) -> None:
        self.name = name
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(self, request: Request, redis: Redis = Depends(get_redis)) -> None:
        limit = self.limit or get_settings().auth_rate_limit_per_minute
        client_ip = request.client.host if request.client else "unknown"
        await enforce_rate_limit(redis, self.name, client_ip, limit, self.window_seconds)
