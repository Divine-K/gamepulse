"""Game-facing API: authenticated with `X-API-Key`; the key identifies the game."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from app.api.achievements import to_out as achievement_out
from app.api.achievements import to_unlock as unlock_out
from app.api.leaderboards import LeaderboardQuery
from app.core.dependencies import ApiKeyGame, DbSession, enforce_game_rate_limit
from app.core.errors import AppError
from app.repositories.achievements import AchievementRepository
from app.repositories.sessions import SessionRepository
from app.schemas.achievement import AchievementBrief, AchievementOut, UnlockOut
from app.schemas.analytics import OverviewOut
from app.schemas.common import Page, Pagination
from app.schemas.event import EventCreate, EventOut
from app.schemas.game import GameOut
from app.schemas.leaderboard import (
    LeaderboardEntry,
    LeaderboardPage,
    Period,
    ScoreOut,
    ScoreSubmit,
)
from app.schemas.player import PlayerCreate, PlayerOut
from app.schemas.session import SessionEnd, SessionEndOut, SessionOut, SessionStart
from app.services.achievements import AchievementService
from app.services.analytics import AnalyticsService
from app.services.events import EventService
from app.services.leaderboards import build_leaderboard
from app.services.players import PlayerService
from app.services.scores import ScoreService
from app.services.sessions import SessionService

router = APIRouter(
    prefix="/api/v1/game", tags=["game api"], dependencies=[Depends(enforce_game_rate_limit)]
)

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
    response_model=SessionEndOut,
    summary="Complete a session with its score and result (idempotent)",
    description=(
        "Updates the player's stats, records the final score and evaluates achievements. "
        "`unlocked_achievements` lists awards created by this call; a repeat call returns the "
        "original session with an empty list."
    ),
)
async def end_session(
    session_id: uuid.UUID, body: SessionEnd, game: ApiKeyGame, db: DbSession
) -> SessionEndOut:
    game_session, unlocked = await SessionService(db, game).end(session_id, body)
    out = SessionEndOut.model_validate(game_session)
    out.unlocked_achievements = [AchievementBrief.model_validate(d) for d in unlocked]
    return out


# --- scores -------------------------------------------------------------------------


@router.post(
    "/scores",
    response_model=ScoreOut,
    status_code=201,
    summary="Submit a score",
    description=(
        "Appends to the score ledger. With a `session_id` and category `score` it also updates "
        "that session's live score. Any other category name creates a separate ranking, "
        "available as the `category:<name>` leaderboard metric."
    ),
)
async def submit_score(body: ScoreSubmit, game: ApiKeyGame, db: DbSession) -> ScoreOut:
    entry = await ScoreService(db, game).submit(body)
    return ScoreOut(
        id=entry.id,
        category=entry.category,
        value=entry.value,
        session_id=entry.session_id,
        created_at=entry.created_at,
    )


# --- leaderboards -------------------------------------------------------------------


@router.get(
    "/leaderboards/{metric}",
    response_model=LeaderboardPage,
    summary="Ranked players for a metric",
    description=(
        "Metrics: `total_score`, `best_score`, `wins`, `achievements`, `completed_sessions`, "
        "or `category:<name>`. Ties share a rank."
    ),
)
async def leaderboard(
    metric: str, game: ApiKeyGame, db: DbSession, params: Annotated[LeaderboardQuery, Depends()]
) -> LeaderboardPage:
    return await build_leaderboard(
        db,
        game.id,
        metric,
        period=params.period,
        q=params.q,
        min_value=params.min_value,
        player_id=None,
        order=params.order,
        limit=params.limit,
        offset=params.offset,
    )


@router.get(
    "/leaderboards/{metric}/players/{external_id}",
    response_model=LeaderboardEntry,
    summary="One player's rank on a leaderboard",
)
async def player_rank(
    metric: str,
    external_id: str,
    game: ApiKeyGame,
    db: DbSession,
    period: Period = "all",
) -> LeaderboardEntry:
    player = await PlayerService(db, game).get_by_external_id(external_id)
    result = await build_leaderboard(
        db,
        game.id,
        metric,
        period=period,
        q=None,
        min_value=None,
        player_id=player.id,
        order="desc",
        limit=1,
        offset=0,
    )
    if not result.items:
        raise AppError("player_not_ranked", "Player has no entry on this leaderboard yet.", 404)
    return result.items[0]


# --- achievements -------------------------------------------------------------------


@router.get(
    "/achievements",
    response_model=list[AchievementOut],
    summary="Enabled achievements for this game",
)
async def achievement_catalogue(game: ApiKeyGame, db: DbSession) -> list[AchievementOut]:
    rows = await AchievementService(db, game).list(only_enabled=True)
    return [achievement_out(d, n, rate) for d, n, rate in rows]


@router.get(
    "/players/{external_id}/achievements",
    response_model=Page[UnlockOut],
    summary="Achievements a player has unlocked",
)
async def player_achievements(
    external_id: str, game: ApiKeyGame, db: DbSession, page: Pagination
) -> Page[UnlockOut]:
    player = await PlayerService(db, game).get_by_external_id(external_id)
    rows, total = await AchievementRepository(db).list_unlocks(
        game.id, player_id=player.id, definition_id=None, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[unlock_out(r) for r in rows], total=total, limit=page.limit, offset=page.offset
    )


# --- events -------------------------------------------------------------------------


@router.post(
    "/events",
    response_model=EventOut,
    status_code=201,
    responses={200: {"description": "Idempotent replay of an earlier request"}},
    summary="Ingest a custom game event",
    description=(
        "Send `player_level_up` (payload `{level, previous_level?}`) or any `custom_<name>` "
        "event with a free-form JSON payload (max 8 KB). Players, sessions, scores and "
        "achievements are recorded automatically; those event types cannot be sent here. "
        "Use an `Idempotency-Key` header to make retries safe."
    ),
)
async def ingest_event(
    body: EventCreate,
    game: ApiKeyGame,
    db: DbSession,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> EventOut:
    event, created = await EventService(db, game).ingest(body, idempotency_key)
    response.status_code = 201 if created else 200
    return EventOut.model_validate(event)


# --- analytics ----------------------------------------------------------------------


@router.get("/analytics/overview", response_model=OverviewOut, summary="Headline statistics")
async def analytics_overview(
    game: ApiKeyGame, db: DbSession, days: int = 30, include_simulated: bool = True
) -> OverviewOut:
    days = min(max(days, 1), 365)
    return await AnalyticsService(db, game.id, include_simulated).overview(days)
