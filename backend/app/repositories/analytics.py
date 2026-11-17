"""Analytics queries. Every figure is an aggregate over real rows; nothing is precomputed."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import Date, Numeric, cast, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AchievementDefinition, Event, GameSession, Player, PlayerAchievement


def utc_day(column):
    """The UTC calendar date of a timestamptz column."""
    return cast(func.timezone("UTC", column), Date)


@dataclass
class WindowRow:
    events: int
    active_players: int
    new_players: int
    sessions: int
    avg_duration: float | None


class AnalyticsRepository:
    def __init__(self, session: AsyncSession, game_id: uuid.UUID, include_simulated: bool) -> None:
        self.session = session
        self.game_id = game_id
        self.include_simulated = include_simulated

    # --- shared filters -------------------------------------------------------------

    def _events(self) -> list:
        conditions = [Event.game_id == self.game_id]
        if not self.include_simulated:
            conditions.append(Event.is_simulated.is_(False))
        return conditions

    def _players(self) -> list:
        conditions = [Player.game_id == self.game_id]
        if not self.include_simulated:
            conditions.append(Player.is_simulated.is_(False))
        return conditions

    def _completed_sessions(self) -> list:
        conditions = [GameSession.game_id == self.game_id, GameSession.status == "completed"]
        if not self.include_simulated:
            conditions.append(GameSession.is_simulated.is_(False))
        return conditions

    # --- totals ---------------------------------------------------------------------

    async def totals(self) -> dict:
        players = await self.session.scalar(
            select(func.count()).select_from(Player).where(*self._players())
        )
        session_conditions = [GameSession.game_id == self.game_id]
        if not self.include_simulated:
            session_conditions.append(GameSession.is_simulated.is_(False))
        sessions = await self.session.scalar(
            select(func.count()).select_from(GameSession).where(*session_conditions)
        )
        completed = (
            await self.session.execute(
                select(func.count(), func.avg(GameSession.duration_seconds)).where(
                    *self._completed_sessions()
                )
            )
        ).one()
        events = await self.session.scalar(
            select(func.count()).select_from(Event).where(*self._events())
        )
        return {
            "total_players": players or 0,
            "total_sessions": sessions or 0,
            "completed_sessions": completed[0] or 0,
            "avg_duration": float(completed[1]) if completed[1] is not None else None,
            "total_events": events or 0,
        }

    async def active_players_since(self, since: datetime) -> int:
        return (
            await self.session.scalar(
                select(func.count(func.distinct(Event.player_id))).where(
                    *self._events(), Event.occurred_at >= since
                )
            )
            or 0
        )

    async def window(self, start: datetime, end: datetime) -> WindowRow:
        in_window = (Event.occurred_at >= start, Event.occurred_at < end)
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count(func.distinct(Event.player_id)),
                    func.count().filter(Event.event_type == "player_registered"),
                    func.count().filter(Event.event_type == "session_started"),
                ).where(*self._events(), *in_window)
            )
        ).one()
        avg = await self.session.scalar(
            select(func.avg(GameSession.duration_seconds)).where(
                *self._completed_sessions(),
                GameSession.ended_at >= start,
                GameSession.ended_at < end,
            )
        )
        return WindowRow(row[0], row[1], row[2], row[3], float(avg) if avg is not None else None)

    # --- time series ----------------------------------------------------------------

    async def daily(self, start: datetime) -> dict[date, dict]:
        day = utc_day(Event.occurred_at).label("day")
        rows = await self.session.execute(
            select(
                day,
                func.count(),
                func.count(func.distinct(Event.player_id)),
                func.count().filter(Event.event_type == "player_registered"),
                func.count().filter(Event.event_type == "session_started"),
                func.count().filter(Event.event_type == "session_ended"),
            )
            .where(*self._events(), Event.occurred_at >= start)
            .group_by(day)
        )
        result = {
            r[0]: {
                "events": r[1],
                "active_players": r[2],
                "new_players": r[3],
                "sessions_started": r[4],
                "sessions_completed": r[5],
                "avg_duration": None,
            }
            for r in rows
        }
        ended_day = utc_day(GameSession.ended_at).label("day")
        durations = await self.session.execute(
            select(ended_day, func.avg(GameSession.duration_seconds))
            .where(*self._completed_sessions(), GameSession.ended_at >= start)
            .group_by(ended_day)
        )
        for d, avg in durations:
            if d in result and avg is not None:
                result[d]["avg_duration"] = float(avg)
        return result

    # --- retention ------------------------------------------------------------------

    async def retention(self, day: int, now: datetime) -> tuple[int, int]:
        """(eligible, retained) for day-N retention: active exactly N days after registering."""
        eligible_filter = (*self._players(), Player.created_at <= now - timedelta(days=day))
        eligible = await self.session.scalar(
            select(func.count()).select_from(Player).where(*eligible_filter)
        )
        came_back = exists().where(
            *self._events(),
            Event.player_id == Player.id,
            Event.occurred_at >= Player.created_at + timedelta(days=day),
            Event.occurred_at < Player.created_at + timedelta(days=day + 1),
        )
        retained = await self.session.scalar(
            select(func.count()).select_from(Player).where(*eligible_filter, came_back)
        )
        return eligible or 0, retained or 0

    # --- score distribution -----------------------------------------------------------

    async def score_summary(
        self,
    ) -> tuple[int, float | None, float | None, float | None, int | None, int | None]:
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.avg(GameSession.score),
                    func.percentile_cont(0.5).within_group(GameSession.score),
                    func.percentile_cont(0.9).within_group(GameSession.score),
                    func.min(GameSession.score),
                    func.max(GameSession.score),
                ).where(*self._completed_sessions())
            )
        ).one()
        f = lambda v: float(v) if v is not None else None  # noqa: E731
        return row[0], f(row[1]), f(row[2]), f(row[3]), row[4], row[5]

    async def score_buckets(self, low: int, width: int) -> dict[int, int]:
        index = func.floor(cast(GameSession.score - low, Numeric) / width).label("bucket")
        rows = await self.session.execute(
            select(index, func.count()).where(*self._completed_sessions()).group_by(index)
        )
        return {int(r[0]): r[1] for r in rows}

    # --- achievements ---------------------------------------------------------------

    async def unlock_counts(self) -> dict[uuid.UUID, int]:
        stmt = (
            select(PlayerAchievement.definition_id, func.count())
            .join(Player, Player.id == PlayerAchievement.player_id)
            .where(PlayerAchievement.game_id == self.game_id, *self._players())
            .group_by(PlayerAchievement.definition_id)
        )
        return {r[0]: r[1] for r in await self.session.execute(stmt)}

    async def definitions(self) -> list[AchievementDefinition]:
        result = await self.session.execute(
            select(AchievementDefinition)
            .where(AchievementDefinition.game_id == self.game_id)
            .order_by(AchievementDefinition.created_at, AchievementDefinition.key)
        )
        return list(result.scalars())

    async def player_count(self) -> int:
        return (
            await self.session.scalar(
                select(func.count()).select_from(Player).where(*self._players())
            )
            or 0
        )

    async def unlocks_by_day(self, start: datetime) -> dict[date, int]:
        day = utc_day(PlayerAchievement.unlocked_at).label("day")
        rows = await self.session.execute(
            select(day, func.count())
            .join(Player, Player.id == PlayerAchievement.player_id)
            .where(
                PlayerAchievement.game_id == self.game_id,
                PlayerAchievement.unlocked_at >= start,
                *self._players(),
            )
            .group_by(day)
        )
        return {r[0]: r[1] for r in rows}
