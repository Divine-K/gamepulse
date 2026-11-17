import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError

from app.core.redis import get_redis
from app.websocket.events import CHANNEL_PATTERN, game_id_from_channel

logger = logging.getLogger("app.realtime")


@dataclass(eq=False)
class Connection:
    """One dashboard WebSocket. Messages are buffered in a bounded queue."""

    websocket: WebSocket | None
    game_id: uuid.UUID
    queue: asyncio.Queue[str | None]
    overflowed: bool = field(default=False)

    @classmethod
    def create(cls, websocket: WebSocket | None, game_id: uuid.UUID, queue_size: int):
        return cls(websocket, game_id, asyncio.Queue(maxsize=queue_size))


class RealtimeHub:
    """Per-process fan-out from Redis pub/sub to local WebSocket connections."""

    def __init__(self, max_connections_per_game: int = 20) -> None:
        self.max_connections_per_game = max_connections_per_game
        self._connections: dict[uuid.UUID, set[Connection]] = {}
        self._pubsub: PubSub | None = None
        self._task: asyncio.Task | None = None

    # --- lifecycle -------------------------------------------------------------------

    async def start(self) -> None:
        """Subscribe before returning, so no event published after startup is missed."""
        self._pubsub = get_redis().pubsub()
        await self._pubsub.psubscribe(CHANNEL_PATTERN)
        self._task = asyncio.create_task(self._listen(), name="realtime-hub")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._pubsub:
            with contextlib.suppress(RedisError, OSError):
                await self._pubsub.aclose()
        self._task = self._pubsub = None

    async def _listen(self) -> None:
        assert self._pubsub is not None
        while True:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message.get("type") == "pmessage":
                    game_id = game_id_from_channel(message["channel"])
                    if game_id is not None:
                        self.dispatch(game_id, message["data"])
            except asyncio.CancelledError:
                raise
            except (RedisError, OSError):
                # redis-py reconnects and resubscribes on the next call; back off meanwhile.
                logger.warning("realtime_hub_redis_error")
                await asyncio.sleep(1.0)

    # --- connections -----------------------------------------------------------------

    def register(self, connection: Connection) -> bool:
        group = self._connections.setdefault(connection.game_id, set())
        if len(group) >= self.max_connections_per_game:
            return False
        group.add(connection)
        return True

    def unregister(self, connection: Connection) -> None:
        group = self._connections.get(connection.game_id)
        if group:
            group.discard(connection)
            if not group:
                del self._connections[connection.game_id]

    def connection_count(self, game_id: uuid.UUID) -> int:
        return len(self._connections.get(game_id, ()))

    def dispatch(self, game_id: uuid.UUID, payload: str) -> None:
        """Queue a payload for every local connection of the game."""
        for connection in list(self._connections.get(game_id, ())):
            try:
                connection.queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Slow client: drop it rather than let it hold memory or block others. The
                # client reconnects and refetches state over REST.
                connection.overflowed = True
                while not connection.queue.empty():
                    connection.queue.get_nowait()
                connection.queue.put_nowait(None)  # tells the sender task to stop
                self.unregister(connection)
