"""Dashboard (JWT) views of a game's players and sessions."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.dependencies import DbSession, OwnedGame
from app.repositories.players import SORT_FIELDS, PlayerRepository
from app.repositories.sessions import SessionRepository
from app.schemas.common import Page, Pagination
from app.schemas.player import PlayerOut
from app.schemas.session import SessionOut, SessionStatus
from app.services.players import PlayerService
from app.services.sessions import SessionService

router = APIRouter(prefix="/api/v1/games/{game_id}", tags=["players and sessions"])

PlayerSort = Literal[
    *SORT_FIELDS, *(f"-{name}" for name in SORT_FIELDS)  # type: ignore[valid-type]
]


@router.get("/players", response_model=Page[PlayerOut], summary="Search and list players")
async def list_players(
    game: OwnedGame,
    db: DbSession,
    page: Pagination,
    q: Annotated[str | None, Query(max_length=100, description="Match username or id")] = None,
    sort: PlayerSort = "-last_active_at",
) -> Page[PlayerOut]:
    players, total = await PlayerRepository(db).list(game.id, q, sort, page.limit, page.offset)
    return Page(
        items=[PlayerOut.model_validate(p) for p in players],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/players/{player_id}", response_model=PlayerOut, summary="Player profile and stats")
async def get_player(game: OwnedGame, player_id: uuid.UUID, db: DbSession) -> PlayerOut:
    return PlayerOut.model_validate(await PlayerService(db, game).get(player_id))


@router.get(
    "/players/{player_id}/sessions",
    response_model=Page[SessionOut],
    summary="A player's session history",
)
async def player_sessions(
    game: OwnedGame, player_id: uuid.UUID, db: DbSession, page: Pagination
) -> Page[SessionOut]:
    player = await PlayerService(db, game).get(player_id)
    sessions, total = await SessionRepository(db).list(
        game.id, status=None, player_id=player.id, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[SessionOut.model_validate(s) for s in sessions],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/sessions", response_model=Page[SessionOut], summary="List sessions")
async def list_sessions(
    game: OwnedGame,
    db: DbSession,
    page: Pagination,
    status: SessionStatus | None = None,
    player_id: uuid.UUID | None = None,
) -> Page[SessionOut]:
    sessions, total = await SessionRepository(db).list(
        game.id, status=status, player_id=player_id, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[SessionOut.model_validate(s) for s in sessions],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/sessions/{session_id}", response_model=SessionOut, summary="Session details")
async def get_session(game: OwnedGame, session_id: uuid.UUID, db: DbSession) -> SessionOut:
    return SessionOut.model_validate(await SessionService(db, game).get(session_id))
