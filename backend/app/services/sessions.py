"""Session lifecycle: active -> completed | abandoned. Invalid transitions return 409."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import AchievementDefinition, Game, GameSession, Player, PlayerStats, ScoreEntry
from app.repositories.players import PlayerRepository
from app.repositories.sessions import SessionRepository
from app.schemas.session import SessionEnd
from app.services import notifications
from app.services.achievements import AchievementEngine


def _session_not_found() -> AppError:
    return AppError("session_not_found", "Session not found.", 404)


def stale_cutoff(now: datetime | None = None) -> datetime:
    timeout = timedelta(minutes=get_settings().session_timeout_minutes)
    return (now or datetime.now(UTC)) - timeout


async def abandon_stale_sessions(session: AsyncSession) -> int:
    """Mark every timed-out active session abandoned. Run periodically by the reaper."""
    repo = SessionRepository(session)
    ids = await repo.abandon_stale(stale_cutoff())
    await session.commit()
    for abandoned in await repo.get_many(ids):
        await notifications.session_abandoned(abandoned.game_id, abandoned)
    return len(ids)


class SessionService:
    def __init__(self, session: AsyncSession, game: Game) -> None:
        self.session = session
        self.game = game
        self.sessions = SessionRepository(session)
        self.players = PlayerRepository(session)

    async def get(self, session_id: uuid.UUID) -> GameSession:
        found = await self.sessions.get(self.game.id, session_id)
        if found is None:
            raise _session_not_found()
        return found

    async def start(
        self, player_external_id: str, idempotency_key: str | None
    ) -> tuple[GameSession, bool]:
        """Start a session. Returns (session, created); created=False for an idempotent replay."""
        player = await self.players.get_by_external_id(self.game.id, player_external_id)
        if player is None:
            raise AppError("player_not_found", "Player not found.", 404)

        if idempotency_key:
            replay = await self._replay(idempotency_key, player)
            if replay:
                return replay, False

        # A crashed client leaves a stale active session; reclaim it instead of blocking forever.
        reclaimed = await self.sessions.abandon_stale(
            stale_cutoff(), game_id=self.game.id, player_id=player.id
        )
        active = await self.sessions.get_active_for_player(self.game.id, player.id)
        if active:
            raise self._already_active(active)

        now = datetime.now(UTC)
        game_session = GameSession(
            game_id=self.game.id,
            player_id=player.id,
            started_at=now,
            last_heartbeat_at=now,
            idempotency_key=idempotency_key,
        )
        self.sessions.add(game_session)
        await self.session.execute(
            update(PlayerStats)
            .where(PlayerStats.player_id == player.id)
            .values(total_sessions=PlayerStats.total_sessions + 1)
        )
        await self._touch_player(player.id, now)
        try:
            await self.session.commit()
        except IntegrityError:
            # Lost a race: a concurrent start created the active session (or reused the key).
            await self.session.rollback()
            if idempotency_key:
                replay = await self._replay(idempotency_key, player)
                if replay:
                    return replay, False
            active = await self.sessions.get_active_for_player(self.game.id, player.id)
            if active:
                raise self._already_active(active) from None
            raise
        started = await self.get(game_session.id)
        for abandoned in await self.sessions.get_many(reclaimed):
            await notifications.session_abandoned(self.game.id, abandoned)
        await notifications.session_started(self.game.id, started)
        return started, True

    async def heartbeat(self, session_id: uuid.UUID) -> GameSession:
        game_session = await self._get_for_update(session_id)
        self._require_active(game_session)
        now = datetime.now(UTC)
        game_session.last_heartbeat_at = now
        await self._touch_player(game_session.player_id, now)
        await self.session.commit()
        await notifications.session_heartbeat(self.game.id, game_session.player_id)
        return await self.get(session_id)

    async def end(
        self, session_id: uuid.UUID, data: SessionEnd
    ) -> tuple[GameSession, list[AchievementDefinition]]:
        """Complete a session. Returns (session, achievements newly unlocked by this call)."""
        game_session = await self._get_for_update(session_id)
        if game_session.status == "completed":
            return game_session, []  # idempotent: never double-count stats or re-award
        self._require_active(game_session)

        now = datetime.now(UTC)
        duration = max(0, int((now - game_session.started_at).total_seconds()))
        final_score = data.score if data.score is not None else game_session.score
        game_session.status = "completed"
        game_session.ended_at = now
        game_session.duration_seconds = duration
        game_session.score = final_score
        game_session.result = data.result
        game_session.last_heartbeat_at = now

        await self.session.execute(
            update(PlayerStats)
            .where(PlayerStats.player_id == game_session.player_id)
            .values(
                completed_sessions=PlayerStats.completed_sessions + 1,
                total_score=PlayerStats.total_score + final_score,
                best_score=func.greatest(PlayerStats.best_score, final_score),
                wins=PlayerStats.wins + (1 if data.result == "win" else 0),
                total_play_seconds=PlayerStats.total_play_seconds + duration,
            )
        )
        self.session.add(
            ScoreEntry(
                game_id=self.game.id,
                player_id=game_session.player_id,
                session_id=game_session.id,
                category="score",
                value=final_score,
            )
        )
        await self.session.flush()
        # Same transaction as the stats update, so the player's totals and awards stay consistent.
        unlocked = await AchievementEngine(self.session, self.game.id).evaluate(
            game_session.player_id, game_session.id
        )
        await self._touch_player(game_session.player_id, now)
        await self.session.commit()
        ended = await self.get(session_id)
        await notifications.session_ended(self.session, self.game.id, ended, unlocked)
        return ended, unlocked

    # --- helpers ---------------------------------------------------------------------

    async def _get_for_update(self, session_id: uuid.UUID) -> GameSession:
        found = await self.sessions.get(self.game.id, session_id, for_update=True)
        if found is None:
            raise _session_not_found()
        return found

    async def _replay(self, key: str, player: Player) -> GameSession | None:
        existing = await self.sessions.get_by_idempotency_key(self.game.id, key)
        if existing is None:
            return None
        if existing.player_id != player.id:
            raise AppError(
                "idempotency_key_reused",
                "This Idempotency-Key was already used for a different player.",
                409,
            )
        return existing

    @staticmethod
    def _already_active(active: GameSession) -> AppError:
        return AppError(
            "session_already_active",
            "This player already has an active session. End it or let it time out.",
            409,
            details=[{"session_id": str(active.id)}],
        )

    @staticmethod
    def _require_active(game_session: GameSession) -> None:
        if game_session.status != "active":
            raise AppError(
                "session_not_active",
                f"Session is {game_session.status}; this action needs an active session.",
                409,
            )

    async def _touch_player(self, player_id: uuid.UUID, when: datetime) -> None:
        await self.session.execute(
            update(Player).where(Player.id == player_id).values(last_active_at=when)
        )
