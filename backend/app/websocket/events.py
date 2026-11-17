"""Real-time event envelope and publishing.

Every event is published to a per-game Redis channel. Each backend process runs one
`RealtimeHub` subscribed to all game channels and forwards messages to its local WebSocket
clients, so any number of API processes stay in sync.
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.exceptions import RedisError

from app.core.redis import get_redis

logger = logging.getLogger("app.realtime")

CHANNEL_PATTERN = "gp:game:*:events"

PLAYER_REGISTERED = "player.registered"
SESSION_STARTED = "session.started"
SESSION_ENDED = "session.ended"
SESSION_ABANDONED = "session.abandoned"
SCORE_SUBMITTED = "score.submitted"
ACHIEVEMENT_UNLOCKED = "achievement.unlocked"
LEADERBOARD_UPDATED = "leaderboard.updated"
EVENT_RECEIVED = "event.received"
SIMULATOR_CLEARED = "simulator.cleared"


def channel_for(game_id: uuid.UUID | str) -> str:
    return f"gp:game:{game_id}:events"


def game_id_from_channel(channel: str) -> uuid.UUID | None:
    parts = channel.split(":")
    if len(parts) != 4 or parts[0] != "gp" or parts[1] != "game" or parts[3] != "events":
        return None
    try:
        return uuid.UUID(parts[2])
    except ValueError:
        return None


def build_envelope(
    game_id: uuid.UUID, event_type: str, data: dict[str, Any], *, is_simulated: bool = False
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "game_id": str(game_id),
        "ts": datetime.now(UTC).isoformat(),
        "is_simulated": is_simulated,
        "data": data,
    }


async def publish(
    game_id: uuid.UUID,
    event_type: str,
    data: dict[str, Any],
    *,
    is_simulated: bool = False,
) -> None:
    """Publish an event. Never raises: real-time is best-effort and must not fail a request.

    The database is the source of truth; clients refetch via REST after a reconnect.
    """
    envelope = build_envelope(game_id, event_type, data, is_simulated=is_simulated)
    try:
        await get_redis().publish(channel_for(game_id), json.dumps(envelope, default=str))
    except (RedisError, OSError):
        logger.warning("realtime_publish_failed", extra={"event_type": event_type})
