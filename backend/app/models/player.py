import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        # (game_id, id) is the target of composite FKs so child rows must share the game.
        UniqueConstraint("game_id", "id", name="uq_players_game_id_id"),
        UniqueConstraint("game_id", "external_id", name="uq_players_game_id_external_id"),
        Index("ix_players_game_id_last_active_at", "game_id", "last_active_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(128))  # the game's own id for the player
    username: Mapped[str] = mapped_column(String(64))
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    is_simulated: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    stats: Mapped["PlayerStats | None"] = relationship(
        primaryjoin="Player.id == PlayerStats.player_id",
        foreign_keys="[PlayerStats.player_id]",
        uselist=False,
        viewonly=True,
        lazy="joined",
    )


class PlayerStats(Base):
    """Denormalized counters, updated in the same transaction as the event that changes them."""

    __tablename__ = "player_stats"
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            ondelete="CASCADE",
            name="fk_player_stats_game_id_player_id_players",
        ),
        Index("ix_player_stats_game_id_total_score", "game_id", "total_score"),
    )

    player_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    game_id: Mapped[uuid.UUID] = mapped_column()
    total_sessions: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    completed_sessions: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_score: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
    best_score: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
    wins: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_play_seconds: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
    achievements_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
