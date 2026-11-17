import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScoreEntry(Base):
    """Append-only score ledger. `category` lets a game keep several scores per player."""

    __tablename__ = "score_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["players.game_id", "players.id"],
            ondelete="CASCADE",
            name="fk_score_entries_game_id_player_id_players",
        ),
        # session_id is optional; when set, the session must belong to the same game.
        ForeignKeyConstraint(
            ["game_id", "session_id"],
            ["game_sessions.game_id", "game_sessions.id"],
            ondelete="CASCADE",
            name="fk_score_entries_game_id_session_id_game_sessions",
        ),
        Index("ix_score_entries_game_id_category_value", "game_id", "category", "value"),
        Index("ix_score_entries_player_id_created_at", "player_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    player_id: Mapped[uuid.UUID] = mapped_column()
    session_id: Mapped[uuid.UUID | None] = mapped_column()
    category: Mapped[str] = mapped_column(String(64), default="score", server_default="score")
    value: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
