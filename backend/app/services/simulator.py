"""The live event simulator: drives a game exactly like an external client would, but every row
it creates is flagged `is_simulated` so it can be told apart and removed without touching real data.

Safety rules enforced here:
  * the simulator can only act on players it created (`is_simulated`), never on real players;
  * cleanup deletes only rows flagged `is_simulated`.
"""

import secrets
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Event, Game, GameSession, Player
from app.repositories.achievements import AchievementRepository
from app.schemas.event import EventCreate
from app.schemas.leaderboard import ScoreSubmit
from app.schemas.player import PlayerCreate
from app.schemas.session import SessionEnd
from app.schemas.simulator import SimEnd, SimEvent, SimSummary
from app.services.achievements import AchievementEngine
from app.services.events import EventService
from app.services.leaderboards import bump_leaderboard_version
from app.services.players import PlayerService
from app.services.scores import ScoreService
from app.services.sessions import SessionService
from app.websocket import events as realtime
from app.websocket import tracker


def _not_simulated() -> AppError:
    return AppError(
        "not_simulated",
        "The simulator can only drive simulated players. Real players are never touched.",
        409,
    )


class SimulatorService:
    def __init__(self, session: AsyncSession, game: Game) -> None:
        self.session = session
        self.game = game
        self.game_id = game.id  # plain id: safe after a rollback
        self.players = PlayerService(session, game)
        self.sessions = SessionService(session, game)

    # --- players ----------------------------------------------------------------------

    async def create_player(self, username: str | None) -> Player:
        token = secrets.token_hex(4)
        data = PlayerCreate(external_id=f"sim_{token}", username=username or f"Sim {token[:4]}")
        player, _ = await self.players.register(data, is_simulated=True)
        return player

    async def list_players(self, limit: int = 50) -> list[Player]:
        result = await self.session.execute(
            select(Player)
            .where(Player.game_id == self.game_id, Player.is_simulated.is_(True))
            .order_by(Player.created_at.desc())
            .limit(limit)
        )
        return list(result.unique().scalars())

    async def _simulated_player(self, player_id: uuid.UUID) -> Player:
        player = await self.players.get(player_id)  # 404 if not in this game
        if not player.is_simulated:
            raise _not_simulated()
        return player

    # --- sessions, scores, events ---------------------------------------------------------

    async def start_session(self, player_id: uuid.UUID) -> GameSession:
        player = await self._simulated_player(player_id)
        game_session, _ = await self.sessions.start(player.external_id, None)
        return game_session

    async def _simulated_session(self, session_id: uuid.UUID) -> GameSession:
        game_session = await self.sessions.get(session_id)
        if not game_session.is_simulated:
            raise _not_simulated()
        return game_session

    async def submit_score(self, session_id: uuid.UUID, value: int):
        game_session = await self._simulated_session(session_id)
        data = ScoreSubmit(
            player_external_id=game_session.player.external_id, value=value, session_id=session_id
        )
        return await ScoreService(self.session, self.game).submit(data)

    async def end_session(self, session_id: uuid.UUID, data: SimEnd):
        await self._simulated_session(session_id)
        return await self.sessions.end(session_id, SessionEnd(score=data.score, result=data.result))

    async def send_event(self, data: SimEvent):
        external_id = None
        if data.player_id is not None:
            external_id = (await self._simulated_player(data.player_id)).external_id
        if data.session_id is not None:
            await self._simulated_session(data.session_id)
        create: EventCreate = data.to_create(external_id)
        event, _ = await EventService(self.session, self.game).ingest(
            create, None, force_simulated=True
        )
        return event

    async def award_achievement(self, player_id: uuid.UUID, achievement_id: uuid.UUID):
        player = await self._simulated_player(player_id)
        definition = await AchievementRepository(self.session).get(self.game_id, achievement_id)
        if definition is None:
            raise AppError("achievement_not_found", "Achievement not found.", 404)
        player_pk = player.id
        awarded = await AchievementEngine(self.session, self.game_id).award(
            definition, player_pk, is_simulated=True
        )
        await self.session.commit()
        if awarded:
            await bump_leaderboard_version(self.game_id)
            await realtime.publish(
                self.game_id,
                realtime.ACHIEVEMENT_UNLOCKED,
                {
                    "player": {
                        "id": str(player_pk),
                        "external_id": player.external_id,
                        "username": player.username,
                        "is_simulated": True,
                    },
                    "achievement": {
                        "id": str(definition.id),
                        "key": definition.key,
                        "name": definition.name,
                        "icon": definition.icon,
                    },
                    "session_id": None,
                },
                is_simulated=True,
            )
        return awarded, definition

    # --- housekeeping -----------------------------------------------------------------------

    async def summary(self) -> SimSummary:
        async def count(model, flag) -> int:
            return (
                await self.session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.game_id == self.game_id, flag.is_(True))
                )
                or 0
            )

        return SimSummary(
            players=await count(Player, Player.is_simulated),
            sessions=await count(GameSession, GameSession.is_simulated),
            events=await count(Event, Event.is_simulated),
        )

    async def clear(self) -> SimSummary:
        """Delete every simulated player, session and event of this game, and nothing else.

        Deleting a player cascades (foreign keys) to its stats, sessions, scores, achievement
        unlocks and events, all of which belong to a simulated player.
        """
        before = await self.summary()
        ids = list(
            (
                await self.session.execute(
                    select(Player.id).where(
                        Player.game_id == self.game_id, Player.is_simulated.is_(True)
                    )
                )
            ).scalars()
        )
        await self.session.execute(
            delete(Event).where(Event.game_id == self.game_id, Event.is_simulated.is_(True))
        )
        await self.session.execute(
            delete(GameSession).where(
                GameSession.game_id == self.game_id, GameSession.is_simulated.is_(True)
            )
        )
        await self.session.execute(
            delete(Player).where(Player.game_id == self.game_id, Player.is_simulated.is_(True))
        )
        await self.session.commit()
        for player_id in ids:
            await tracker.remove(self.game_id, player_id)
        await bump_leaderboard_version(self.game_id)
        await realtime.publish(
            self.game_id, realtime.SIMULATOR_CLEARED, {"deleted": before.model_dump()}
        )
        return before
