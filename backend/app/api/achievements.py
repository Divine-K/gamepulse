"""Dashboard (JWT) achievement management."""

import uuid

from fastapi import APIRouter

from app.core.dependencies import DbSession, OwnedGame
from app.repositories.achievements import AchievementRepository
from app.schemas.achievement import (
    AchievementBrief,
    AchievementCreate,
    AchievementOut,
    AchievementUpdate,
    UnlockOut,
)
from app.schemas.common import Page, Pagination
from app.schemas.player import PlayerBrief
from app.services.achievements import AchievementService
from app.services.players import PlayerService

router = APIRouter(prefix="/api/v1/games/{game_id}", tags=["achievements"])


def to_out(definition, unlock_count: int = 0, unlock_rate: float = 0.0) -> AchievementOut:
    out = AchievementOut.model_validate(definition)
    out.unlock_count, out.unlock_rate = unlock_count, round(unlock_rate, 4)
    return out


def to_unlock(row) -> UnlockOut:
    unlock, definition, player = row
    return UnlockOut(
        id=unlock.id,
        unlocked_at=unlock.unlocked_at,
        session_id=unlock.session_id,
        achievement=AchievementBrief.model_validate(definition),
        player=PlayerBrief.model_validate(player),
    )


@router.get(
    "/achievements",
    response_model=list[AchievementOut],
    summary="Achievement definitions with unlock statistics",
)
async def list_achievements(game: OwnedGame, db: DbSession) -> list[AchievementOut]:
    rows = await AchievementService(db, game).list()
    return [to_out(d, n, rate) for d, n, rate in rows]


@router.post("/achievements", response_model=AchievementOut, status_code=201)
async def create_achievement(
    game: OwnedGame, body: AchievementCreate, db: DbSession
) -> AchievementOut:
    return to_out(await AchievementService(db, game).create(body))


# Declared before /achievements/{id} so "unlocks" is not parsed as an id.
@router.get(
    "/achievements/unlocks",
    response_model=Page[UnlockOut],
    summary="Recent achievement unlocks across all players",
)
async def list_unlocks(
    game: OwnedGame,
    db: DbSession,
    page: Pagination,
    player_id: uuid.UUID | None = None,
    achievement_id: uuid.UUID | None = None,
) -> Page[UnlockOut]:
    rows, total = await AchievementRepository(db).list_unlocks(
        game.id,
        player_id=player_id,
        definition_id=achievement_id,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[to_unlock(r) for r in rows], total=total, limit=page.limit, offset=page.offset
    )


@router.get("/achievements/{achievement_id}", response_model=AchievementOut)
async def get_achievement(
    game: OwnedGame, achievement_id: uuid.UUID, db: DbSession
) -> AchievementOut:
    service = AchievementService(db, game)
    definition = await service.get(achievement_id)
    rows = {d.id: (n, rate) for d, n, rate in await service.list()}
    return to_out(definition, *rows.get(definition.id, (0, 0.0)))


@router.patch(
    "/achievements/{achievement_id}",
    response_model=AchievementOut,
    summary="Edit name, threshold or enabled state",
)
async def update_achievement(
    game: OwnedGame, achievement_id: uuid.UUID, body: AchievementUpdate, db: DbSession
) -> AchievementOut:
    service = AchievementService(db, game)
    definition = await service.update(achievement_id, body)
    rows = {d.id: (n, rate) for d, n, rate in await service.list()}
    return to_out(definition, *rows.get(definition.id, (0, 0.0)))


@router.get(
    "/players/{player_id}/achievements",
    response_model=Page[UnlockOut],
    summary="A player's achievement history",
)
async def player_achievements(
    game: OwnedGame, player_id: uuid.UUID, db: DbSession, page: Pagination
) -> Page[UnlockOut]:
    player = await PlayerService(db, game).get(player_id)
    rows, total = await AchievementRepository(db).list_unlocks(
        game.id, player_id=player.id, definition_id=None, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[to_unlock(r) for r in rows], total=total, limit=page.limit, offset=page.offset
    )
