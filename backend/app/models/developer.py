import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Developer(Base):
    __tablename__ = "developers"
    __table_args__ = (CheckConstraint("role IN ('developer', 'admin')", name="role_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="developer", server_default="developer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Tokens issued before this moment are rejected (set when the password changes).
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
