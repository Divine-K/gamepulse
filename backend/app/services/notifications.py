"""Turn domain changes into real-time events, active-player updates and cache invalidation.

Called by services *after* the database commit succeeds. Everything here is best-effort and
never raises, so a Redis outage cannot fail a game's API request.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AchievementDefinition, GameSession, Player, ScoreEntry
from app.repositories.leaderboards import LeaderboardRepository
from app.services.leaderboards import bump_leaderboard_version
from app.websocket import events, tracker


def player_dict(player: Player) -> dict[str, Any]:
    return {"id": str(player.id), "external_id": player.external_id, "username": player.username}


def session_dict(game_session: GameSession) -> dict[str, Any]:
    return {
        "id": str(game_session.id),
        "status": game_session.status,
        "result": game_session.result,
        "score": game_session.score,
        "started_at": game_session.started_at.isoformat(),
        "ended_at": game_session.ended_at.isoformat() if game_session.ended_at else None,
        "duration_seconds": game_session.duration_seconds,
        "player": player_dict(game_session.player),
    }


async def player_registered(game_id: uuid.UUID, player: Player) -> None:
    await events.publish(
        game_id,
        events.PLAYER_REGISTERED,
        {"player": player_dict(player)},
        is_simulated=player.is_simulated,
    )


async def session_started(game_id: uuid.UUID, game_session: GameSession) -> None:
    await tracker.touch(game_id, game_session.player_id)
    await events.publish(
        game_id,
        events.SESSION_STARTED,
        {
            "session": session_dict(game_session),
            "active_players": await tracker.count_from_redis(game_id),
        },
        is_simulated=game_session.is_simulated,
    )


async def session_heartbeat(game_id: uuid.UUID, player_id: uuid.UUID) -> None:
    await tracker.touch(game_id, player_id)


async def session_abandoned(game_id: uuid.UUID, game_session: GameSession) -> None:
    await tracker.remove(game_id, game_session.player_id)
    await events.publish(
        game_id,
        events.SESSION_ABANDONED,
        {
            "session": session_dict(game_session),
            "active_players": await tracker.count_from_redis(game_id),
        },
        is_simulated=game_session.is_simulated,
    )


async def session_ended(
    db: AsyncSession,
    game_id: uuid.UUID,
    game_session: GameSession,
    unlocked: list[AchievementDefinition],
) -> None:
    await tracker.remove(game_id, game_session.player_id)
    await bump_leaderboard_version(game_id)
    simulated = game_session.is_simulated
    player = game_session.player
    await events.publish(
        game_id,
        events.SESSION_ENDED,
        {
            "session": session_dict(game_session),
            "active_players": await tracker.count_from_redis(game_id),
        },
        is_simulated=simulated,
    )
    for definition in unlocked:
        await events.publish(
            game_id,
            events.ACHIEVEMENT_UNLOCKED,
            {
                "player": player_dict(player),
                "achievement": {
                    "id": str(definition.id),
                    "key": definition.key,
                    "name": definition.name,
                    "icon": definition.icon,
                },
                "session_id": str(game_session.id),
            },
            is_simulated=simulated,
        )
    rank = await LeaderboardRepository(db).total_score_rank(game_id, game_session.player_id)
    await events.publish(
        game_id,
        events.LEADERBOARD_UPDATED,
        {
            "metric": "total_score",
            "player": player_dict(player),
            "rank": rank,
            "session_score": game_session.score,
        },
        is_simulated=simulated,
    )


async def score_submitted(game_id: uuid.UUID, player: Player, entry: ScoreEntry) -> None:
    await bump_leaderboard_version(game_id)
    await events.publish(
        game_id,
        events.SCORE_SUBMITTED,
        {
            "player": player_dict(player),
            "category": entry.category,
            "value": entry.value,
            "session_id": str(entry.session_id) if entry.session_id else None,
        },
        is_simulated=player.is_simulated,
    )
