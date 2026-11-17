import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Types the platform records itself when the matching action happens. External callers cannot
# submit these (they would be double counted); they use the dedicated endpoints instead.
SYSTEM_EVENT_TYPES = (
    "player_registered",
    "session_started",
    "session_ended",
    "score_submitted",
    "achievement_unlocked",
)


class Event(Base):
    """Append-only activity log. Analytics are computed from this table and `game_sessions`."""

    __tablename__ = "events"
    __table_args__ = (
        # Player and session are optional, but when set they must belong to the same game.
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            ondelete="CASCADE",
            name="fk_events_game_id_player_id_players",
        ),
        ForeignKeyConstraint(
            ["game_id", "session_id"],
            ["game_sessions.game_id", "game_sessions.id"],
            ondelete="CASCADE",
            name="fk_events_game_id_session_id_game_sessions",
        ),
        CheckConstraint("event_type ~ '^[a-z][a-z0-9_]{0,63}$'", name="event_type_format"),
        Index(
            "uq_events_game_id_idempotency_key",
            "game_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_events_game_id_occurred_at", "game_id", "occurred_at"),
        Index("ix_events_game_id_event_type_occurred_at", "game_id", "event_type", "occurred_at"),
        Index("ix_events_player_id_occurred_at", "player_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    player_id: Mapped[uuid.UUID | None] = mapped_column()
    session_id: Mapped[uuid.UUID | None] = mapped_column()
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    is_simulated: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
