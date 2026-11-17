import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    AchievementAnalyticsOut,
    AchievementStat,
    EngagementOut,
    EngagementPoint,
    OverviewOut,
    RetentionOut,
    RetentionPoint,
    ScoreBucket,
    ScoreDistributionOut,
    UnlockDay,
    WindowStats,
)
from app.websocket import tracker

RETENTION_DAYS = (1, 7, 30)


def _window_stats(row) -> WindowStats:
    return WindowStats(
        new_players=row.new_players,
        sessions=row.sessions,
        active_players=row.active_players,
        events=row.events,
        avg_session_duration_seconds=row.avg_duration,
    )


class AnalyticsService:
    def __init__(self, session: AsyncSession, game_id: uuid.UUID, include_simulated: bool) -> None:
        self.session = session
        self.game_id = game_id
        self.include_simulated = include_simulated
        self.repo = AnalyticsRepository(session, game_id, include_simulated)

    async def overview(self, days: int) -> OverviewOut:
        now = datetime.now(UTC)
        period = timedelta(days=days)
        totals = await self.repo.totals()
        current = await self.repo.window(now - period, now + timedelta(seconds=1))
        previous = await self.repo.window(now - 2 * period, now - period)
        active_now, source = await tracker.active_players(self.session, self.game_id)
        return OverviewOut(
            total_players=totals["total_players"],
            total_sessions=totals["total_sessions"],
            completed_sessions=totals["completed_sessions"],
            total_events=totals["total_events"],
            avg_session_duration_seconds=totals["avg_duration"],
            daily_active_players=await self.repo.active_players_since(now - timedelta(days=1)),
            monthly_active_players=await self.repo.active_players_since(now - timedelta(days=30)),
            currently_active_players=active_now,
            currently_active_source=source,
            period_days=days,
            current=_window_stats(current),
            previous=_window_stats(previous),
            include_simulated=self.include_simulated,
        )

    async def engagement(self, days: int) -> EngagementOut:
        today = datetime.now(UTC).date()
        first_day = today - timedelta(days=days - 1)
        start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)
        data = await self.repo.daily(start)
        points = []
        for offset in range(days):  # every day appears, including quiet ones (as zeros)
            day = first_day + timedelta(days=offset)
            row = data.get(day)
            points.append(
                EngagementPoint(
                    date=day,
                    active_players=row["active_players"] if row else 0,
                    new_players=row["new_players"] if row else 0,
                    sessions_started=row["sessions_started"] if row else 0,
                    sessions_completed=row["sessions_completed"] if row else 0,
                    avg_session_duration_seconds=row["avg_duration"] if row else None,
                    events=row["events"] if row else 0,
                )
            )
        return EngagementOut(days=days, points=points, include_simulated=self.include_simulated)

    async def retention(self) -> RetentionOut:
        now = datetime.now(UTC)
        points = []
        for day in RETENTION_DAYS:
            eligible, retained = await self.repo.retention(day, now)
            rate = round(retained / eligible, 4) if eligible else None
            points.append(
                RetentionPoint(
                    day=day, eligible_players=eligible, retained_players=retained, rate=rate
                )
            )
        return RetentionOut(points=points, include_simulated=self.include_simulated)

    async def scores(self, buckets: int) -> ScoreDistributionOut:
        count, average, median, p90, low, high = await self.repo.score_summary()
        result_buckets: list[ScoreBucket] = []
        if count and low is not None and high is not None:
            width = max(1, math.ceil((high - low + 1) / buckets))
            counts = await self.repo.score_buckets(low, width)
            for index in range(math.ceil((high - low + 1) / width)):
                start = low + index * width
                result_buckets.append(
                    ScoreBucket(start=start, end=start + width - 1, count=counts.get(index, 0))
                )
        return ScoreDistributionOut(
            completed_sessions=count,
            average=average,
            median=median,
            p90=p90,
            min=low,
            max=high,
            buckets=result_buckets,
            include_simulated=self.include_simulated,
        )

    async def achievements(self, days: int) -> AchievementAnalyticsOut:
        counts = await self.repo.unlock_counts()
        players = await self.repo.player_count()
        stats = [
            AchievementStat(
                key=d.key,
                name=d.name,
                icon=d.icon,
                is_enabled=d.is_enabled,
                unlock_count=counts.get(d.id, 0),
                unlock_rate=round(counts.get(d.id, 0) / players, 4) if players else 0.0,
            )
            for d in await self.repo.definitions()
        ]
        today = datetime.now(UTC).date()
        first_day = today - timedelta(days=days - 1)
        by_day = await self.repo.unlocks_by_day(
            datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)
        )
        return AchievementAnalyticsOut(
            total_unlocks=sum(counts.values()),
            achievements=stats,
            unlocks_by_day=[
                UnlockDay(
                    date=first_day + timedelta(days=i),
                    count=by_day.get(first_day + timedelta(days=i), 0),
                )
                for i in range(days)
            ],
            days=days,
            include_simulated=self.include_simulated,
        )
