"""Achievement definitions and the evaluation engine.

Evaluation is rule-based: each `condition_type` maps to an evaluator function. Adding a new
condition type means writing one evaluator and adding it to `EVALUATORS` (plus the enum/CHECK).
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import AchievementDefinition, Game, PlayerAchievement, PlayerStats
from app.repositories.achievements import AchievementRepository
from app.repositories.leaderboards import LeaderboardRepository
from app.schemas.achievement import AchievementCreate, AchievementUpdate

# Seeded for every new game; developers can edit, disable or add to them.
DEFAULT_ACHIEVEMENTS = [
    (
        "first_game",
        "First Game",
        "Complete your first session.",
        "sessions_completed",
        1,
        "play",
        True,
    ),
    (
        "dedicated_player",
        "Dedicated Player",
        "Complete 10 sessions.",
        "sessions_completed",
        10,
        "flame",
        True,
    ),
    (
        "high_scorer",
        "High Scorer",
        "Reach a score of 1,000 in one session.",
        "score_reached",
        1000,
        "target",
        True,
    ),
    (
        "veteran",
        "Veteran",
        "Play for a total of one hour.",
        "total_play_seconds",
        3600,
        "clock",
        True,
    ),
    ("winner", "Winner", "Win 5 sessions.", "wins", 5, "medal", True),
    (
        "champion",
        "Champion",
        "Reach #1 on the total score leaderboard. Enable once you have several players.",
        "leaderboard_rank",
        1,
        "crown",
        False,
    ),
]


@dataclass
class EvalContext:
    game_id: uuid.UUID
    player_id: uuid.UUID
    stats: PlayerStats
    leaderboards: LeaderboardRepository
    _rank: int | None = field(default=None, init=False)
    _rank_loaded: bool = field(default=False, init=False)

    async def rank(self) -> int | None:
        if not self._rank_loaded:
            self._rank = await self.leaderboards.total_score_rank(self.game_id, self.player_id)
            self._rank_loaded = True
        return self._rank


Evaluator = Callable[[EvalContext, int], Awaitable[bool]]


async def _sessions_completed(ctx: EvalContext, threshold: int) -> bool:
    return ctx.stats.completed_sessions >= threshold


async def _score_reached(ctx: EvalContext, threshold: int) -> bool:
    return ctx.stats.best_score >= threshold  # best single-session score


async def _total_play_seconds(ctx: EvalContext, threshold: int) -> bool:
    return ctx.stats.total_play_seconds >= threshold


async def _wins(ctx: EvalContext, threshold: int) -> bool:
    return ctx.stats.wins >= threshold


async def _leaderboard_rank(ctx: EvalContext, threshold: int) -> bool:
    rank = await ctx.rank()
    return rank is not None and rank <= threshold


EVALUATORS: dict[str, Evaluator] = {
    "sessions_completed": _sessions_completed,
    "score_reached": _score_reached,
    "total_play_seconds": _total_play_seconds,
    "wins": _wins,
    "leaderboard_rank": _leaderboard_rank,
}


class AchievementEngine:
    """Awards achievements. Safe to call repeatedly: the DB unique key prevents duplicates."""

    def __init__(self, session: AsyncSession, game_id: uuid.UUID) -> None:
        self.session = session
        self.game_id = game_id
        self.definitions = AchievementRepository(session)
        self.leaderboards = LeaderboardRepository(session)

    async def evaluate(
        self, player_id: uuid.UUID, session_id: uuid.UUID | None = None
    ) -> list[AchievementDefinition]:
        pending = await self.definitions.pending_for_player(self.game_id, player_id)
        if not pending:
            return []
        stats = await self.session.scalar(
            select(PlayerStats)
            .where(PlayerStats.player_id == player_id)
            .execution_options(populate_existing=True)
        )
        if stats is None:
            return []
        ctx = EvalContext(self.game_id, player_id, stats, self.leaderboards)

        unlocked: list[AchievementDefinition] = []
        for definition in pending:
            evaluator = EVALUATORS[definition.condition_type]
            if not await evaluator(ctx, definition.threshold):
                continue
            inserted = await self.session.execute(
                insert(PlayerAchievement)
                .values(
                    game_id=self.game_id,
                    player_id=player_id,
                    definition_id=definition.id,
                    session_id=session_id,
                )
                .on_conflict_do_nothing(index_elements=["player_id", "definition_id"])
                .returning(PlayerAchievement.id)
            )
            if inserted.first() is not None:  # False if a concurrent call awarded it first
                unlocked.append(definition)

        if unlocked:
            await self.session.execute(
                update(PlayerStats)
                .where(PlayerStats.player_id == player_id)
                .values(achievements_count=PlayerStats.achievements_count + len(unlocked))
            )
        return unlocked


class AchievementService:
    def __init__(self, session: AsyncSession, game: Game) -> None:
        self.session = session
        self.game = game
        self.repo = AchievementRepository(session)

    async def list(
        self, *, only_enabled: bool = False
    ) -> list[tuple[AchievementDefinition, int, float]]:
        rows = await self.repo.list_with_counts(self.game.id, only_enabled=only_enabled)
        players = await self.repo.count_players(self.game.id)
        return [(d, n, (n / players) if players else 0.0) for d, n in rows]

    async def get(self, definition_id: uuid.UUID) -> AchievementDefinition:
        found = await self.repo.get(self.game.id, definition_id)
        if found is None:
            raise AppError("achievement_not_found", "Achievement not found.", 404)
        return found

    async def create(self, data: AchievementCreate) -> AchievementDefinition:
        if await self.repo.key_exists(self.game.id, data.key):
            raise AppError("achievement_key_taken", "An achievement with this key exists.", 409)
        definition = AchievementDefinition(game_id=self.game.id, **data.model_dump())
        self.repo.add(definition)
        await self.session.commit()
        await self.session.refresh(definition)
        return definition

    async def update(
        self, definition_id: uuid.UUID, data: AchievementUpdate
    ) -> AchievementDefinition:
        definition = await self.get(definition_id)
        for name, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(definition, name, value)
        await self.session.commit()
        await self.session.refresh(definition)
        return definition


def seed_default_achievements(session: AsyncSession, game_id: uuid.UUID) -> None:
    for key, name, description, condition, threshold, icon, enabled in DEFAULT_ACHIEVEMENTS:
        session.add(
            AchievementDefinition(
                game_id=game_id,
                key=key,
                name=name,
                description=description,
                condition_type=condition,
                threshold=threshold,
                icon=icon,
                is_enabled=enabled,
            )
        )
