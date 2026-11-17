import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AchievementDefinition, Player, PlayerAchievement


class AchievementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, definition: AchievementDefinition) -> None:
        self.session.add(definition)

    async def get(
        self, game_id: uuid.UUID, definition_id: uuid.UUID
    ) -> AchievementDefinition | None:
        result = await self.session.execute(
            select(AchievementDefinition).where(
                AchievementDefinition.game_id == game_id,
                AchievementDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def key_exists(self, game_id: uuid.UUID, key: str) -> bool:
        return bool(
            await self.session.scalar(
                select(func.count())
                .select_from(AchievementDefinition)
                .where(AchievementDefinition.game_id == game_id, AchievementDefinition.key == key)
            )
        )

    async def list_with_counts(
        self, game_id: uuid.UUID, *, only_enabled: bool = False
    ) -> list[tuple[AchievementDefinition, int]]:
        unlocks = func.count(PlayerAchievement.id)
        stmt = (
            select(AchievementDefinition, unlocks)
            .outerjoin(
                PlayerAchievement, PlayerAchievement.definition_id == AchievementDefinition.id
            )
            .where(AchievementDefinition.game_id == game_id)
            .group_by(AchievementDefinition.id)
            .order_by(AchievementDefinition.created_at, AchievementDefinition.key)
        )
        if only_enabled:
            stmt = stmt.where(AchievementDefinition.is_enabled.is_(True))
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result]

    async def pending_for_player(
        self, game_id: uuid.UUID, player_id: uuid.UUID
    ) -> list[AchievementDefinition]:
        """Enabled definitions this player has not unlocked yet."""
        unlocked = exists().where(
            PlayerAchievement.definition_id == AchievementDefinition.id,
            PlayerAchievement.player_id == player_id,
        )
        result = await self.session.execute(
            select(AchievementDefinition).where(
                AchievementDefinition.game_id == game_id,
                AchievementDefinition.is_enabled.is_(True),
                ~unlocked,
            )
        )
        return list(result.scalars())

    async def list_unlocks(
        self,
        game_id: uuid.UUID,
        *,
        player_id: uuid.UUID | None,
        definition_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[PlayerAchievement, AchievementDefinition, Player]], int]:
        conditions = [PlayerAchievement.game_id == game_id]
        if player_id:
            conditions.append(PlayerAchievement.player_id == player_id)
        if definition_id:
            conditions.append(PlayerAchievement.definition_id == definition_id)
        total = await self.session.scalar(
            select(func.count()).select_from(PlayerAchievement).where(*conditions)
        )
        result = await self.session.execute(
            select(PlayerAchievement, AchievementDefinition, Player)
            .join(
                AchievementDefinition, AchievementDefinition.id == PlayerAchievement.definition_id
            )
            .join(Player, Player.id == PlayerAchievement.player_id)
            .where(*conditions)
            .order_by(PlayerAchievement.unlocked_at.desc(), PlayerAchievement.id)
            .limit(limit)
            .offset(offset)
        )
        return [(r[0], r[1], r[2]) for r in result.unique()], total or 0

    async def count_players(self, game_id: uuid.UUID) -> int:
        return (
            await self.session.scalar(
                select(func.count()).select_from(Player).where(Player.game_id == game_id)
            )
            or 0
        )
