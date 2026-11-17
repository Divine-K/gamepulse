import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    achievements,
    admin,
    analytics,
    auth,
    events,
    game_api,
    games,
    health,
    leaderboards,
    players,
    realtime,
)
from app.core.config import get_settings
from app.core.database import dispose_engine, get_session_factory
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.redis import close_redis
from app.services.sessions import abandon_stale_sessions
from app.websocket import tracker
from app.websocket.hub import RealtimeHub

logger = logging.getLogger("app.reaper")


async def _reap_stale_sessions_forever(interval_seconds: int) -> None:
    """Periodically mark sessions with no heartbeat as abandoned."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with get_session_factory()() as session:
                count = await abandon_stale_sessions(session)
            if count:
                logger.info("abandoned_stale_sessions", extra={"count": count})
        except Exception:
            logger.exception("session_reaper_failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    hub = RealtimeHub(settings.ws_max_connections_per_game)
    app.state.hub = hub
    await hub.start()
    try:
        async with get_session_factory()() as session:
            restored = await tracker.rebuild(session)
        logger.info("active_tracker_rebuilt", extra={"players": restored})
    except Exception:
        logger.exception("active_tracker_rebuild_failed")
    reaper = None
    if settings.session_reaper_interval_seconds > 0 and settings.app_env != "test":
        reaper = asyncio.create_task(
            _reap_stale_sessions_forever(settings.session_reaper_interval_seconds)
        )
    yield
    if reaper:
        reaper.cancel()
        with suppress(asyncio.CancelledError):
            await reaper
    await hub.stop()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="Game backend and analytics platform.",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    for router in (
        health.router,
        auth.router,
        games.router,
        players.router,
        achievements.router,
        leaderboards.router,
        events.router,
        analytics.router,
        realtime.router,
        game_api.router,
        admin.router,
    ):
        app.include_router(router)
    return app


app = create_app()
