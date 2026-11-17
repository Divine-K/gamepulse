import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

CONDITION_TYPES = (
    "sessions_completed",
    "score_reached",
    "total_play_seconds",
    "wins",
    "leaderboard_rank",
)


class AchievementDefinition(Base):
    __tablename__ = "achievement_definitions"
    __table_args__ = (
        UniqueConstraint("game_id", "id", name="uq_achievement_definitions_game_id_id"),
        UniqueConstraint("game_id", "key", name="uq_achievement_definitions_game_id_key"),
        CheckConstraint(
            "condition_type IN ({})".format(", ".join(f"'{c}'" for c in CONDITION_TYPES)),
            name="condition_type_valid",
        ),
        CheckConstraint("threshold >= 1", name="threshold_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    condition_type: Mapped[str] = mapped_column(String(32))
    threshold: Mapped[int] = mapped_column(BigInteger)
    icon: Mapped[str] = mapped_column(String(32), default="trophy", server_default="trophy")
    is_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlayerAchievement(Base):
    __tablename__ = "player_achievements"
    __table_args__ = (
        # Duplicate-award prevention, enforced by the database.
        UniqueConstraint(
            "player_id", "definition_id", name="uq_player_achievements_player_definition"
        ),
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            ondelete="CASCADE",
            name="fk_player_achievements_game_id_player_id_players",
        ),
        ForeignKeyConstraint(
            ["game_id", "definition_id"],
            ["achievement_definitions.game_id", "achievement_definitions.id"],
            ondelete="CASCADE",
            name="fk_player_achievements_game_id_definition_id_definitions",
        ),
        Index("ix_player_achievements_game_id_unlocked_at", "game_id", "unlocked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    player_id: Mapped[uuid.UUID] = mapped_column()
    definition_id: Mapped[uuid.UUID] = mapped_column()
    session_id: Mapped[uuid.UUID | None] = mapped_column()  # the session that triggered it
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
