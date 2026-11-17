"""Game-facing API: authenticated with `X-API-Key`; the key identifies the game."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Response

from app.core.dependencies import ApiKeyGame, DbSession
from app.repositories.sessions import SessionRepository
from app.schemas.common import Page, Pagination
from app.schemas.game import GameOut
from app.schemas.player import PlayerCreate, PlayerOut
from app.schemas.session import SessionEnd, SessionOut, SessionStart
from app.services.players import PlayerService
from app.services.sessions import SessionService

router = APIRouter(prefix="/api/v1/game", tags=["game api"])

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        max_length=128,
        description="Retry-safe key. Replaying it returns the original result.",
    ),
]


@router.get("/me", response_model=GameOut, summary="Verify an API key and return its game")
async def whoami(game: ApiKeyGame) -> GameOut:
    return GameOut.model_validate(game)


# --- players ------------------------------------------------------------------------


@router.post(
    "/players",
    response_model=PlayerOut,
    status_code=201,
    responses={200: {"description": "Player already existed; returned unchanged"}},
    summary="Register a player (idempotent by external_id)",
)
async def register_player(
    body: PlayerCreate, game: ApiKeyGame, db: DbSession, response: Response
) -> PlayerOut:
    player, created = await PlayerService(db, game).register(body)
    response.status_code = 201 if created else 200
    return PlayerOut.model_validate(player)


@router.get(
    "/players/{external_id}", response_model=PlayerOut, summary="Get a player profile and stats"
)
async def get_player(external_id: str, game: ApiKeyGame, db: DbSession) -> PlayerOut:
    return PlayerOut.model_validate(await PlayerService(db, game).get_by_external_id(external_id))


@router.get(
    "/players/{external_id}/sessions",
    response_model=Page[SessionOut],
    summary="A player's session history, newest first",
)
async def player_sessions(
    external_id: str, game: ApiKeyGame, db: DbSession, page: Pagination
) -> Page[SessionOut]:
    player = await PlayerService(db, game).get_by_external_id(external_id)
    sessions, total = await SessionRepository(db).list(
        game.id, status=None, player_id=player.id, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[SessionOut.model_validate(s) for s in sessions],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


# --- sessions -----------------------------------------------------------------------


@router.post(
    "/sessions",
    response_model=SessionOut,
    status_code=201,
    responses={
        200: {"description": "Idempotent replay of an earlier request"},
        409: {"description": "Player already has an active session"},
    },
    summary="Start a game session",
)
async def start_session(
    body: SessionStart,
    game: ApiKeyGame,
    db: DbSession,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> SessionOut:
    game_session, created = await SessionService(db, game).start(
        body.player_external_id, idempotency_key
    )
    response.status_code = 201 if created else 200
    return SessionOut.model_validate(game_session)


@router.get("/sessions/{session_id}", response_model=SessionOut, summary="Get a session")
async def get_session(session_id: uuid.UUID, game: ApiKeyGame, db: DbSession) -> SessionOut:
    return SessionOut.model_validate(await SessionService(db, game).get(session_id))


@router.post(
    "/sessions/{session_id}/heartbeat",
    response_model=SessionOut,
    summary="Keep an active session alive",
)
async def heartbeat(session_id: uuid.UUID, game: ApiKeyGame, db: DbSession) -> SessionOut:
    return SessionOut.model_validate(await SessionService(db, game).heartbeat(session_id))


@router.post(
    "/sessions/{session_id}/end",
    response_model=SessionOut,
    summary="Complete a session with its score and result (idempotent)",
)
async def end_session(
    session_id: uuid.UUID, body: SessionEnd, game: ApiKeyGame, db: DbSession
) -> SessionOut:
    return SessionOut.model_validate(await SessionService(db, game).end(session_id, body))
