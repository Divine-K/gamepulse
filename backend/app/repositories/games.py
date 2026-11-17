import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, Game


class GameRepository:
    """All queries are scoped by developer, so one tenant can never read another's games."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, game: Game) -> None:
        self.session.add(game)

    async def get_owned(self, game_id: uuid.UUID, developer_id: uuid.UUID) -> Game | None:
        result = await self.session.execute(
            select(Game).where(
                Game.id == game_id,
                Game.developer_id == developer_id,
                Game.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_owned(
        self, developer_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[Game], int]:
        live = (Game.developer_id == developer_id, Game.deleted_at.is_(None))
        total = await self.session.scalar(select(func.count()).select_from(Game).where(*live))
        result = await self.session.execute(
            select(Game)
            .where(*live)
            .order_by(Game.created_at.desc(), Game.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars()), total or 0

    async def slug_exists(self, developer_id: uuid.UUID, slug: str) -> bool:
        result = await self.session.scalar(
            select(func.count())
            .select_from(Game)
            .where(
                Game.developer_id == developer_id,
                Game.slug == slug,
                Game.deleted_at.is_(None),
            )
        )
        return bool(result)

    async def soft_delete(self, game: Game) -> None:
        now = datetime.now(UTC)
        game.deleted_at = now
        # Deleting a game invalidates all of its keys.
        keys = await self.session.execute(
            select(ApiKey).where(ApiKey.game_id == game.id, ApiKey.revoked_at.is_(None))
        )
        for key in keys.scalars():
            key.revoked_at = now
