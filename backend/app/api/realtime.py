"""Dashboard real-time: WebSocket stream and live counters."""

import asyncio
import contextlib
import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.dependencies import DbSession, OwnedGame
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.repositories.developers import DeveloperRepository
from app.repositories.games import GameRepository
from app.websocket import tracker
from app.websocket.hub import Connection, RealtimeHub

logger = logging.getLogger("app.realtime")

router = APIRouter(tags=["real-time"])

# Close codes (4000-4999 are application-defined).
CLOSE_BAD_MESSAGE = 4400
CLOSE_UNAUTHORIZED = 4401
CLOSE_NOT_FOUND = 4404
CLOSE_AUTH_TIMEOUT = 4408
CLOSE_TOO_MANY = 4429
CLOSE_SLOW_CONSUMER = 1013  # "try again later": reconnect and refetch


class LiveStats(BaseModel):
    active_players: int
    source: Literal["redis", "postgres"]
    dashboards_connected: int


@router.get("/api/v1/games/{game_id}/live", response_model=LiveStats, summary="Live counters")
async def live_stats(game: OwnedGame, db: DbSession, request: Request) -> LiveStats:
    """Currently active players (Redis, falling back to Postgres) and open dashboards."""
    count, source = await tracker.active_players(db, game.id)
    hub: RealtimeHub | None = getattr(request.app.state, "hub", None)
    return LiveStats(
        active_players=count,
        source=source,  # type: ignore[arg-type]
        dashboards_connected=hub.connection_count(game.id) if hub else 0,
    )


async def _authorize(token: str, game_id: uuid.UUID) -> bool:
    """True if the JWT belongs to an active developer who owns the game."""
    claims = decode_access_token(token)  # raises AppError on a bad token
    developer_id = uuid.UUID(claims["sub"])
    async with get_session_factory()() as db:
        developer = await DeveloperRepository(db).get(developer_id)
        if developer is None or not developer.is_active:
            raise AppError("invalid_token", "Invalid or expired token.", 401)
        return await GameRepository(db).get_owned(game_id, developer.id) is not None


@router.websocket("/api/v1/ws/games/{game_id}")
async def game_stream(websocket: WebSocket, game_id: uuid.UUID) -> None:
    """Live event stream for one game.

    Protocol: connect, then send `{"type":"auth","token":"<jwt>"}` as the first message (the
    token is never put in the URL, where it would leak into logs). The server replies
    `{"type":"ready"}` and then pushes event envelopes. `{"type":"ping"}` gets `{"type":"pong"}`.
    Close codes: 4400 bad message, 4401 unauthorized, 4404 game not found, 4408 auth timeout,
    4429 too many connections, 1013 client too slow (reconnect and refetch over REST).
    """
    settings = get_settings()
    await websocket.accept()

    try:
        first = await asyncio.wait_for(websocket.receive_text(), settings.ws_auth_timeout_seconds)
    except TimeoutError:
        await websocket.close(CLOSE_AUTH_TIMEOUT, "auth timeout")
        return
    except WebSocketDisconnect:
        return
    try:
        message = json.loads(first)
        token = message["token"] if message.get("type") == "auth" else None
    except (ValueError, TypeError, KeyError, AttributeError):
        token = None
    if not isinstance(token, str):
        await websocket.close(CLOSE_BAD_MESSAGE, "first message must be auth")
        return

    try:
        owns_game = await _authorize(token, game_id)
    except (AppError, ValueError):
        await websocket.close(CLOSE_UNAUTHORIZED, "unauthorized")
        return
    if not owns_game:
        # Same code for "not yours" and "does not exist": no cross-tenant existence leak.
        await websocket.close(CLOSE_NOT_FOUND, "game not found")
        return

    hub: RealtimeHub = websocket.app.state.hub
    connection = Connection.create(websocket, game_id, settings.ws_queue_size)
    if not hub.register(connection):
        await websocket.close(CLOSE_TOO_MANY, "too many connections for this game")
        return

    try:
        async with get_session_factory()() as db:
            active, _ = await tracker.active_players(db, game_id)
        await websocket.send_json(
            {"type": "ready", "game_id": str(game_id), "active_players": active}
        )

        sender = asyncio.create_task(_send_loop(connection))
        receiver = asyncio.create_task(_receive_loop(connection))
        done, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in (*done, *pending):
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await task
        if connection.overflowed:
            with contextlib.suppress(RuntimeError):
                await websocket.close(CLOSE_SLOW_CONSUMER, "client too slow")
    finally:
        hub.unregister(connection)


async def _send_loop(connection: Connection) -> None:
    assert connection.websocket is not None
    while True:
        payload = await connection.queue.get()
        if payload is None:
            return
        await connection.websocket.send_text(payload)


async def _receive_loop(connection: Connection) -> None:
    assert connection.websocket is not None
    while True:
        text = await connection.websocket.receive_text()
        try:
            message = json.loads(text)
        except ValueError:
            continue
        if isinstance(message, dict) and message.get("type") == "ping":
            with contextlib.suppress(asyncio.QueueFull):
                connection.queue.put_nowait(json.dumps({"type": "pong"}))
