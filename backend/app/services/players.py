import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Game, Player, PlayerStats
from app.repositories.players import PlayerRepository
from app.schemas.player import PlayerCreate


def player_not_found() -> AppError:
    return AppError("player_not_found", "Player not found.", 404)


class PlayerService:
    """Player operations for one game (the tenant), already authorized by the caller."""

    def __init__(self, session: AsyncSession, game: Game) -> None:
        self.session = session
        self.game = game
        self.players = PlayerRepository(session)

    async def register(self, data: PlayerCreate) -> tuple[Player, bool]:
        """Idempotent by external_id. Returns (player, created)."""
        existing = await self.players.get_by_external_id(self.game.id, data.external_id)
        if existing:
            return existing, False

        player_id = uuid.uuid4()
        player = Player(
            id=player_id,
            game_id=self.game.id,
            external_id=data.external_id,
            username=data.username or data.external_id[:64],
            meta=data.metadata,
        )
        stats = PlayerStats(player_id=player_id, game_id=self.game.id)
        self.players.add(player, stats)
        try:
            await self.session.commit()
        except IntegrityError:  # concurrent registration of the same external_id
            await self.session.rollback()
            existing = await self.players.get_by_external_id(self.game.id, data.external_id)
            if existing is None:
                raise
            return existing, False
        await self.session.refresh(player, ["stats"])
        return player, True

    async def get_by_external_id(self, external_id: str) -> Player:
        player = await self.players.get_by_external_id(self.game.id, external_id)
        if player is None:
            raise player_not_found()
        return player

    async def get(self, player_id: uuid.UUID) -> Player:
        player = await self.players.get(self.game.id, player_id)
        if player is None:
            raise player_not_found()
        return player
