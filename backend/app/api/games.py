import uuid

from fastapi import APIRouter, Response

from app.core.dependencies import CurrentDeveloper, DbSession, OwnedGame
from app.repositories.games import GameRepository
from app.schemas.common import Page, Pagination
from app.schemas.game import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    GameCreate,
    GameOut,
    GameUpdate,
)
from app.services.games import GameService

router = APIRouter(prefix="/api/v1/games", tags=["games"])


@router.get("", response_model=Page[GameOut], summary="List your games")
async def list_games(developer: CurrentDeveloper, db: DbSession, page: Pagination) -> Page[GameOut]:
    games, total = await GameRepository(db).list_owned(developer.id, page.limit, page.offset)
    return Page(
        items=[GameOut.model_validate(g) for g in games],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("", response_model=GameOut, status_code=201, summary="Register a game")
async def create_game(body: GameCreate, developer: CurrentDeveloper, db: DbSession) -> GameOut:
    return GameOut.model_validate(await GameService(db).create_game(developer, body))


@router.get("/{game_id}", response_model=GameOut, summary="Get a game")
async def get_game(game: OwnedGame) -> GameOut:
    return GameOut.model_validate(game)


@router.patch("/{game_id}", response_model=GameOut, summary="Edit a game")
async def update_game(game: OwnedGame, body: GameUpdate, db: DbSession) -> GameOut:
    return GameOut.model_validate(await GameService(db).update_game(game, body))


@router.delete("/{game_id}", status_code=204, summary="Delete a game and revoke its keys")
async def delete_game(game: OwnedGame, db: DbSession) -> Response:
    await GameService(db).delete_game(game)
    return Response(status_code=204)


# --- API keys -----------------------------------------------------------------------


@router.get("/{game_id}/api-keys", response_model=list[ApiKeyOut], summary="List API keys")
async def list_api_keys(game: OwnedGame, db: DbSession) -> list[ApiKeyOut]:
    keys = await GameService(db).keys.list_for_game(game.id)
    return [ApiKeyOut.model_validate(k) for k in keys]


@router.post(
    "/{game_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=201,
    summary="Create an API key (secret shown once)",
)
async def create_api_key(game: OwnedGame, body: ApiKeyCreate, db: DbSession) -> ApiKeyCreated:
    key, secret = await GameService(db).create_key(game, body.name)
    return ApiKeyCreated(**ApiKeyOut.model_validate(key).model_dump(), key=secret)


@router.post(
    "/{game_id}/api-keys/{key_id}/rotate",
    response_model=ApiKeyCreated,
    status_code=201,
    summary="Rotate a key: revoke it and issue a replacement",
)
async def rotate_api_key(game: OwnedGame, key_id: uuid.UUID, db: DbSession) -> ApiKeyCreated:
    key, secret = await GameService(db).rotate_key(game, key_id)
    return ApiKeyCreated(**ApiKeyOut.model_validate(key).model_dump(), key=secret)


@router.delete("/{game_id}/api-keys/{key_id}", status_code=204, summary="Revoke an API key")
async def revoke_api_key(game: OwnedGame, key_id: uuid.UUID, db: DbSession) -> Response:
    await GameService(db).revoke_key(game, key_id)
    return Response(status_code=204)
