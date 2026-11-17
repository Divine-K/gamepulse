"""Dashboard (JWT) event log."""

import uuid
from datetime import datetime

from fastapi import APIRouter

from app.core.dependencies import DbSession, OwnedGame
from app.repositories.events import EventRepository
from app.schemas.common import Page, Pagination
from app.schemas.event import EventWithPlayer
from app.schemas.player import PlayerBrief

router = APIRouter(prefix="/api/v1/games/{game_id}", tags=["events"])


@router.get(
    "/events",
    response_model=Page[EventWithPlayer],
    summary="Event log, newest first",
    description="Filter by type, player, session and time range. Also serves player timelines.",
)
async def list_events(
    game: OwnedGame,
    db: DbSession,
    page: Pagination,
    event_type: str | None = None,
    player_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    include_simulated: bool = True,
) -> Page[EventWithPlayer]:
    rows, total = await EventRepository(db).list(
        game.id,
        event_type=event_type,
        player_id=player_id,
        session_id=session_id,
        since=since,
        until=until,
        include_simulated=include_simulated,
        limit=page.limit,
        offset=page.offset,
    )
    items = []
    for event, player in rows:
        out = EventWithPlayer.model_validate(event)
        out.player = PlayerBrief.model_validate(player) if player else None
        items.append(out)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
