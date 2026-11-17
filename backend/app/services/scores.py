from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Game, Player, ScoreEntry
from app.repositories.players import PlayerRepository
from app.repositories.sessions import SessionRepository
from app.schemas.leaderboard import SCORE_CATEGORY_PATTERN, ScoreSubmit
from app.services import notifications
from app.services.event_log import record_event


class ScoreService:
    def __init__(self, session: AsyncSession, game: Game) -> None:
        self.session = session
        self.game = game
        self.players = PlayerRepository(session)
        self.sessions = SessionRepository(session)

    async def submit(self, data: ScoreSubmit) -> ScoreEntry:
        """Record a score in the ledger. For category 'score' inside a session it also becomes
        the session's live score (the final score is set when the session ends)."""
        if not SCORE_CATEGORY_PATTERN.match(data.category):
            raise AppError("invalid_category", "category must match [a-z0-9_]{1,64}.", 422)
        player = await self.players.get_by_external_id(self.game.id, data.player_external_id)
        if player is None:
            raise AppError("player_not_found", "Player not found.", 404)

        if data.session_id is not None:
            game_session = await self.sessions.get(self.game.id, data.session_id, for_update=True)
            if game_session is None or game_session.player_id != player.id:
                raise AppError("session_not_found", "Session not found for this player.", 404)
            if game_session.status != "active":
                raise AppError(
                    "session_not_active",
                    f"Session is {game_session.status}; cannot add scores.",
                    409,
                )
            if data.category == "score":
                game_session.score = data.value

        entry = ScoreEntry(
            game_id=self.game.id,
            player_id=player.id,
            session_id=data.session_id,
            category=data.category,
            value=data.value,
        )
        self.session.add(entry)
        record_event(
            self.session,
            game_id=self.game.id,
            event_type="score_submitted",
            player_id=player.id,
            session_id=data.session_id,
            payload={"category": data.category, "value": data.value},
            is_simulated=player.is_simulated,
        )
        await self.session.execute(
            update(Player).where(Player.id == player.id).values(last_active_at=datetime.now(UTC))
        )
        await self.session.commit()
        await self.session.refresh(entry)
        await notifications.score_submitted(self.game.id, player, entry)
        return entry
