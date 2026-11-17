import logging
import time

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis import get_redis

logger = logging.getLogger("app.rate_limit")


class RateLimiter:
    """Fixed-window limiter per client IP, backed by Redis. Use as a route dependency.

    Fails open if Redis is unavailable, so an outage doesn't lock everyone out of login.
    Behind a reverse proxy, configure the proxy headers so `request.client` is the real IP.
    """

    def __init__(self, name: str, limit: int | None = None, window_seconds: int = 60) -> None:
        self.name = name
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(self, request: Request, redis: Redis = Depends(get_redis)) -> None:
        limit = self.limit or get_settings().auth_rate_limit_per_minute
        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time() // self.window_seconds)
        key = f"gp:rl:{self.name}:{client_ip}:{window}"
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, self.window_seconds * 2)
        except RedisError:
            logger.warning("rate_limit_unavailable", extra={"limiter": self.name})
            return
        if count > limit:
            retry_after = self.window_seconds - int(time.time() % self.window_seconds)
            raise AppError(
                "rate_limited",
                "Too many requests. Please slow down.",
                429,
                headers={"Retry-After": str(retry_after)},
            )
