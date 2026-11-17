"""Authentication and authorization dependencies shared by all routers."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.rate_limit import enforce_rate_limit
from app.core.redis import get_redis
from app.core.security import decode_access_token
from app.models import Developer, Game
from app.repositories.developers import DeveloperRepository
from app.repositories.games import GameRepository
from app.services.games import GameService

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _unauthorized(code: str, message: str) -> AppError:
    return AppError(code, message, 401, headers={"WWW-Authenticate": "Bearer"})


async def get_current_developer(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Developer:
    if credentials is None:
        raise _unauthorized("not_authenticated", "Authentication required.")
    claims = decode_access_token(credentials.credentials)
    try:
        developer_id = uuid.UUID(claims["sub"])
    except ValueError:
        raise _unauthorized("invalid_token", "Invalid or expired token.") from None
    developer = await DeveloperRepository(db).get(developer_id)
    if developer is None or not developer.is_active:
        raise _unauthorized("invalid_token", "Invalid or expired token.")
    return developer


CurrentDeveloper = Annotated[Developer, Depends(get_current_developer)]


def require_role(*roles: str) -> Callable[[Developer], Awaitable[Developer]]:
    async def checker(developer: CurrentDeveloper) -> Developer:
        if developer.role not in roles:
            raise AppError("forbidden", "You do not have permission to do this.", 403)
        return developer

    return checker


async def get_owned_game(game_id: uuid.UUID, developer: CurrentDeveloper, db: DbSession) -> Game:
    """Resolve `/games/{game_id}` only if the caller owns it.

    Foreign and deleted games both return 404 so existence is never leaked across tenants.
    """
    game = await GameRepository(db).get_owned(game_id, developer.id)
    if game is None:
        raise AppError("game_not_found", "Game not found.", 404)
    return game


OwnedGame = Annotated[Game, Depends(get_owned_game)]


async def get_game_from_api_key(
    db: DbSession,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Game:
    """Game-facing authentication: the API key identifies the game (the tenant)."""
    return await GameService(db).authenticate_api_key(x_api_key)


ApiKeyGame = Annotated[Game, Depends(get_game_from_api_key)]


async def enforce_game_rate_limit(
    game: ApiKeyGame, redis: Annotated[Redis, Depends(get_redis)]
) -> None:
    """Limit each game's API traffic (all of its keys together) per minute."""
    await enforce_rate_limit(
        redis, "game_api", str(game.id), get_settings().game_api_rate_limit_per_minute
    )
