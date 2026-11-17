import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Player


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_idempotency_key(self, game_id: uuid.UUID, key: str) -> Event | None:
        result = await self.session.execute(
            select(Event).where(Event.game_id == game_id, Event.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        game_id: uuid.UUID,
        *,
        event_type: str | None,
        player_id: uuid.UUID | None,
        session_id: uuid.UUID | None,
        since: datetime | None,
        until: datetime | None,
        include_simulated: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[Event, Player | None]], int]:
        conditions = [Event.game_id == game_id]
        if event_type:
            conditions.append(Event.event_type == event_type)
        if player_id:
            conditions.append(Event.player_id == player_id)
        if session_id:
            conditions.append(Event.session_id == session_id)
        if since:
            conditions.append(Event.occurred_at >= since)
        if until:
            conditions.append(Event.occurred_at < until)
        if not include_simulated:
            conditions.append(Event.is_simulated.is_(False))

        total = await self.session.scalar(
            select(func.count()).select_from(Event).where(*conditions)
        )
        result = await self.session.execute(
            select(Event, Player)
            .outerjoin(Player, Player.id == Event.player_id)
            .where(*conditions)
            .order_by(Event.occurred_at.desc(), Event.id)
            .limit(limit)
            .offset(offset)
        )
        return [(row[0], row[1]) for row in result.unique()], total or 0
