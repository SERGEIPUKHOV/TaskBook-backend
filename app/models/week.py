from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Week(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "weeks"
    __table_args__ = (UniqueConstraint("user_id", "year", "week_number", name="uq_weeks_user_period"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    reward: Mapped[str | None] = mapped_column(Text, nullable=True)
