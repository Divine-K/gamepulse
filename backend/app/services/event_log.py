"""Persist activity as events. Called inside the same transaction as the action itself."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event


def record_event(
    session: AsyncSession,
    *,
    game_id: uuid.UUID,
    event_type: str,
    player_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    is_simulated: bool = False,
    occurred_at: datetime | None = None,
    idempotency_key: str | None = None,
) -> Event:
    """Add an event to the unit of work. The caller commits.

    Rows referenced by player_id/session_id must already be flushed (the ORM has no
    relationship to order the inserts, and the composite foreign keys would reject them).
    """
    event = Event(
        game_id=game_id,
        player_id=player_id,
        session_id=session_id,
        event_type=event_type,
        payload=payload or {},
        is_simulated=is_simulated,
        idempotency_key=idempotency_key,
    )
    if occurred_at is not None:
        event.occurred_at = occurred_at
    session.add(event)
    return event
