import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.player import Player


class GameSession(Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        UniqueConstraint("game_id", "id", name="uq_game_sessions_game_id_id"),
        # A session can only link a player of the same game.
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            ondelete="CASCADE",
            name="fk_game_sessions_game_id_player_id_players",
        ),
        CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="status_valid"),
        CheckConstraint("result IS NULL OR result IN ('win', 'loss', 'draw')", name="result_valid"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ended_after_started"),
        CheckConstraint("score >= 0", name="score_non_negative"),
        # At most one active session per player per game.
        Index(
            "uq_game_sessions_one_active_per_player",
            "game_id",
            "player_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        # Idempotent session creation.
        Index(
            "uq_game_sessions_game_id_idempotency_key",
            "game_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_game_sessions_game_id_started_at", "game_id", "started_at"),
        Index("ix_game_sessions_player_id_started_at", "player_id", "started_at"),
        Index("ix_game_sessions_status_last_heartbeat_at", "status", "last_heartbeat_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    player_id: Mapped[uuid.UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    result: Mapped[str | None] = mapped_column(String(10))
    score: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    is_simulated: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    player: Mapped[Player] = relationship(
        primaryjoin=(
            "and_(GameSession.game_id == Player.game_id, GameSession.player_id == Player.id)"
        ),
        foreign_keys="[GameSession.game_id, GameSession.player_id]",
        viewonly=True,
        lazy="joined",
    )
