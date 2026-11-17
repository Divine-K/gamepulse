import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Player, PlayerStats

SORT_FIELDS = {
    "created_at": Player.created_at,
    "last_active_at": Player.last_active_at,
    "username": Player.username,
    "total_score": PlayerStats.total_score,
    "best_score": PlayerStats.best_score,
    "total_sessions": PlayerStats.total_sessions,
}


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PlayerRepository:
    """Every method takes `game_id`: there is no way to read a player without a game."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, player: Player, stats: PlayerStats) -> None:
        self.session.add_all([player, stats])

    async def get(self, game_id: uuid.UUID, player_id: uuid.UUID) -> Player | None:
        result = await self.session.execute(
            select(Player).where(Player.game_id == game_id, Player.id == player_id)
        )
        return result.unique().scalar_one_or_none()

    async def get_by_external_id(self, game_id: uuid.UUID, external_id: str) -> Player | None:
        result = await self.session.execute(
            select(Player).where(Player.game_id == game_id, Player.external_id == external_id)
        )
        return result.unique().scalar_one_or_none()

    async def list(
        self, game_id: uuid.UUID, q: str | None, sort: str, limit: int, offset: int
    ) -> tuple[list[Player], int]:
        conditions = [Player.game_id == game_id]
        if q:
            pattern = f"%{_escape_like(q)}%"
            conditions.append(
                Player.username.ilike(pattern, escape="\\")
                | Player.external_id.ilike(pattern, escape="\\")
            )
        descending = sort.startswith("-")
        column = SORT_FIELDS[sort.lstrip("-")]
        order = column.desc() if descending else column.asc()

        total = await self.session.scalar(
            select(func.count()).select_from(Player).where(*conditions)
        )
        result = await self.session.execute(
            select(Player)
            .join(PlayerStats, PlayerStats.player_id == Player.id)
            .where(*conditions)
            .order_by(order, Player.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.unique().scalars()), total or 0
