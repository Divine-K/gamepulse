"""Live event simulator (dashboard, JWT). Drives a game with simulated players."""

import uuid

from fastapi import APIRouter

from app.core.dependencies import DbSession, OwnedGame
from app.schemas.achievement import AchievementBrief
from app.schemas.common import Page
from app.schemas.event import EventOut
from app.schemas.leaderboard import ScoreOut
from app.schemas.player import PlayerOut
from app.schemas.session import SessionEndOut, SessionOut
from app.schemas.simulator import (
    SimAward,
    SimAwardResult,
    SimCleared,
    SimEnd,
    SimEvent,
    SimPlayerCreate,
    SimScore,
    SimSessionStart,
    SimSummary,
)
from app.services.simulator import SimulatorService

router = APIRouter(prefix="/api/v1/games/{game_id}/simulator", tags=["simulator"])


@router.get("/summary", response_model=SimSummary, summary="How much simulated data exists")
async def summary(game: OwnedGame, db: DbSession) -> SimSummary:
    return await SimulatorService(db, game).summary()


@router.get("/players", response_model=Page[PlayerOut], summary="Simulated players")
async def list_players(game: OwnedGame, db: DbSession) -> Page[PlayerOut]:
    players = await SimulatorService(db, game).list_players()
    items = [PlayerOut.model_validate(p) for p in players]
    return Page(items=items, total=len(items), limit=50, offset=0)


@router.post("/players", response_model=PlayerOut, status_code=201, summary="Create a test player")
async def create_player(game: OwnedGame, body: SimPlayerCreate, db: DbSession) -> PlayerOut:
    return PlayerOut.model_validate(await SimulatorService(db, game).create_player(body.username))


@router.post("/sessions", response_model=SessionOut, status_code=201, summary="Start a session")
async def start_session(game: OwnedGame, body: SimSessionStart, db: DbSession) -> SessionOut:
    return SessionOut.model_validate(await SimulatorService(db, game).start_session(body.player_id))


@router.post(
    "/sessions/{session_id}/score",
    response_model=ScoreOut,
    status_code=201,
    summary="Send a live score update",
)
async def send_score(
    game: OwnedGame, session_id: uuid.UUID, body: SimScore, db: DbSession
) -> ScoreOut:
    entry = await SimulatorService(db, game).submit_score(session_id, body.value)
    return ScoreOut(
        id=entry.id,
        category=entry.category,
        value=entry.value,
        session_id=entry.session_id,
        created_at=entry.created_at,
    )


@router.post("/sessions/{session_id}/end", response_model=SessionEndOut, summary="End a session")
async def end_session(
    game: OwnedGame, session_id: uuid.UUID, body: SimEnd, db: DbSession
) -> SessionEndOut:
    game_session, unlocked = await SimulatorService(db, game).end_session(session_id, body)
    out = SessionEndOut.model_validate(game_session)
    out.unlocked_achievements = [AchievementBrief.model_validate(d) for d in unlocked]
    return out


@router.post("/events", response_model=EventOut, status_code=201, summary="Send a custom event")
async def send_event(game: OwnedGame, body: SimEvent, db: DbSession) -> EventOut:
    return EventOut.model_validate(await SimulatorService(db, game).send_event(body))


@router.post(
    "/players/{player_id}/achievements",
    response_model=SimAwardResult,
    summary="Award an achievement to a simulated player",
)
async def award(
    game: OwnedGame, player_id: uuid.UUID, body: SimAward, db: DbSession
) -> SimAwardResult:
    awarded, definition = await SimulatorService(db, game).award_achievement(
        player_id, body.achievement_id
    )
    return SimAwardResult(awarded=awarded, achievement_key=definition.key)


@router.delete(
    "/data",
    response_model=SimCleared,
    summary="Delete all simulated data (never touches real data)",
)
async def clear(game: OwnedGame, db: DbSession) -> SimCleared:
    return SimCleared(deleted=await SimulatorService(db, game).clear())
