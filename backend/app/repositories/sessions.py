import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GameSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, game_session: GameSession) -> None:
        self.session.add(game_session)

    async def get(
        self, game_id: uuid.UUID, session_id: uuid.UUID, *, for_update: bool = False
    ) -> GameSession | None:
        stmt = select(GameSession).where(
            GameSession.game_id == game_id, GameSession.id == session_id
        )
        if for_update:
            # Serialize concurrent end/heartbeat calls on the same session.
            stmt = stmt.with_for_update(of=GameSession)
        # populate_existing refreshes objects already in the identity map (e.g. just-created
        # sessions) so the joined `player` relationship is loaded for serialization.
        result = await self.session.execute(stmt.execution_options(populate_existing=True))
        return result.unique().scalar_one_or_none()

    async def get_active_for_player(
        self, game_id: uuid.UUID, player_id: uuid.UUID
    ) -> GameSession | None:
        result = await self.session.execute(
            select(GameSession).where(
                GameSession.game_id == game_id,
                GameSession.player_id == player_id,
                GameSession.status == "active",
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_by_idempotency_key(self, game_id: uuid.UUID, key: str) -> GameSession | None:
        result = await self.session.execute(
            select(GameSession).where(
                GameSession.game_id == game_id, GameSession.idempotency_key == key
            )
        )
        return result.unique().scalar_one_or_none()

    async def list(
        self,
        game_id: uuid.UUID,
        *,
        status: str | None,
        player_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[GameSession], int]:
        conditions = [GameSession.game_id == game_id]
        if status:
            conditions.append(GameSession.status == status)
        if player_id:
            conditions.append(GameSession.player_id == player_id)
        total = await self.session.scalar(
            select(func.count()).select_from(GameSession).where(*conditions)
        )
        result = await self.session.execute(
            select(GameSession)
            .where(*conditions)
            .order_by(GameSession.started_at.desc(), GameSession.id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.unique().scalars()), total or 0

    async def abandon_stale(
        self,
        cutoff: datetime,
        *,
        game_id: uuid.UUID | None = None,
        player_id: uuid.UUID | None = None,
    ) -> int:
        """Mark active sessions with no heartbeat since `cutoff` as abandoned."""
        stmt = (
            update(GameSession)
            .where(GameSession.status == "active", GameSession.last_heartbeat_at < cutoff)
            .values(
                status="abandoned",
                ended_at=GameSession.last_heartbeat_at,
                duration_seconds=func.greatest(
                    0,
                    func.floor(
                        func.extract(
                            "epoch", GameSession.last_heartbeat_at - GameSession.started_at
                        )
                    ),
                ).cast(GameSession.duration_seconds.type),
            )
            .execution_options(synchronize_session=False)
        )
        if game_id:
            stmt = stmt.where(GameSession.game_id == game_id)
        if player_id:
            stmt = stmt.where(GameSession.player_id == player_id)
        result = await self.session.execute(stmt)
        return result.rowcount or 0
