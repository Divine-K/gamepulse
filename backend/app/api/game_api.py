"""Game-facing API: authenticated with `X-API-Key`; the key identifies the game."""

from fastapi import APIRouter

from app.core.dependencies import ApiKeyGame
from app.schemas.game import GameOut

router = APIRouter(prefix="/api/v1/game", tags=["game api"])


@router.get("/me", response_model=GameOut, summary="Verify an API key and return its game")
async def whoami(game: ApiKeyGame) -> GameOut:
    return GameOut.model_validate(game)
