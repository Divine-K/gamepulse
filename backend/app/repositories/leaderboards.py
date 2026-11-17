import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Player, PlayerStats, ScoreEntry
from app.schemas.leaderboard import SCORE_CATEGORY_PATTERN

# Metrics backed by the denormalized player_stats row. Add a line to add a ranking category.
STAT_METRICS = {
    "total_score": PlayerStats.total_score,
    "best_score": PlayerStats.best_score,
    "wins": PlayerStats.wins,
    "achievements": PlayerStats.achievements_count,
    "completed_sessions": PlayerStats.completed_sessions,
}
CATEGORY_PREFIX = "category:"  # e.g. category:speedrun_ms ranks each player's best ledger value
PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}


def validate_metric(metric: str) -> None:
    if metric in STAT_METRICS:
        return
    if metric.startswith(CATEGORY_PREFIX) and SCORE_CATEGORY_PATTERN.match(
        metric[len(CATEGORY_PREFIX) :]
    ):
        return
    raise AppError(
        "unknown_metric",
        f"Unknown metric. Use one of {sorted(STAT_METRICS)} or '{CATEGORY_PREFIX}<name>'.",
        422,
    )


class LeaderboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base(self, game_id: uuid.UUID, metric: str, period: str) -> Select:
        if metric in STAT_METRICS:
            if period != "all":
                raise AppError(
                    "period_not_supported",
                    "Periods only apply to 'category:<name>' metrics, which are ledger-based.",
                    422,
                )
            column = STAT_METRICS[metric]
            return select(PlayerStats.player_id.label("player_id"), column.label("value")).where(
                PlayerStats.game_id == game_id, column > 0
            )
        category = metric[len(CATEGORY_PREFIX) :]
        stmt = select(
            ScoreEntry.player_id.label("player_id"), func.max(ScoreEntry.value).label("value")
        ).where(ScoreEntry.game_id == game_id, ScoreEntry.category == category)
        if period != "all":
            cutoff = datetime.now(UTC) - timedelta(days=PERIOD_DAYS[period])
            stmt = stmt.where(ScoreEntry.created_at >= cutoff)
        return stmt.group_by(ScoreEntry.player_id)

    async def page(
        self,
        game_id: uuid.UUID,
        metric: str,
        *,
        period: str = "all",
        q: str | None = None,
        min_value: int | None = None,
        player_id: uuid.UUID | None = None,
        order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[int, int, Player]], int]:
        validate_metric(metric)
        base = self._base(game_id, metric, period).subquery()
        # Rank over ALL players first, then filter: a search never changes anyone's rank.
        ranked = select(
            base.c.player_id,
            base.c.value,
            func.rank().over(order_by=base.c.value.desc()).label("rank"),
        ).subquery()

        conditions = [Player.game_id == game_id]
        if q:
            pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            conditions.append(
                Player.username.ilike(pattern, escape="\\")
                | Player.external_id.ilike(pattern, escape="\\")
            )
        if min_value is not None:
            conditions.append(ranked.c.value >= min_value)
        if player_id is not None:
            conditions.append(Player.id == player_id)

        joined = select(ranked.c.rank, ranked.c.value, Player).join(
            Player, Player.id == ranked.c.player_id
        )
        total = await self.session.scalar(
            select(func.count()).select_from(joined.where(*conditions).subquery())
        )
        rank_order = ranked.c.rank.asc() if order == "desc" else ranked.c.rank.desc()
        result = await self.session.execute(
            joined.where(*conditions).order_by(rank_order, Player.id).limit(limit).offset(offset)
        )
        rows = [(row.rank, row.value, row.Player) for row in result.unique()]
        return rows, total or 0

    async def total_score_rank(self, game_id: uuid.UUID, player_id: uuid.UUID) -> int | None:
        """Competition rank by total_score, or None if the player has no score yet."""
        mine = await self.session.scalar(
            select(PlayerStats.total_score).where(PlayerStats.player_id == player_id)
        )
        if not mine:
            return None
        ahead = await self.session.scalar(
            select(func.count())
            .select_from(PlayerStats)
            .where(PlayerStats.game_id == game_id, PlayerStats.total_score > mine)
        )
        return (ahead or 0) + 1
