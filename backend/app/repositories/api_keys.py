import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, Game


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, key: ApiKey) -> None:
        self.session.add(key)

    async def list_for_game(self, game_id: uuid.UUID) -> list[ApiKey]:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.game_id == game_id).order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars())

    async def get_for_game(self, game_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.game_id == game_id, ApiKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def get_active_with_game(self, prefix: str) -> tuple[ApiKey, Game] | None:
        """Look up a non-revoked key whose game has not been deleted."""
        result = await self.session.execute(
            select(ApiKey, Game)
            .join(Game, Game.id == ApiKey.game_id)
            .where(
                ApiKey.key_prefix == prefix,
                ApiKey.revoked_at.is_(None),
                Game.deleted_at.is_(None),
            )
        )
        row = result.first()
        return (row[0], row[1]) if row else None
