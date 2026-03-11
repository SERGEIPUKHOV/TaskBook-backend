from __future__ import annotations

from datetime import date

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Habit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "habits"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    starts_at_month_key: Mapped[str | None] = mapped_column(String(7), index=True, nullable=True)
    ends_before_month_key: Mapped[str | None] = mapped_column(String(7), index=True, nullable=True)


class HabitLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "habit_logs"
    __table_args__ = (UniqueConstraint("habit_id", "date", name="uq_habit_logs_habit_date"),)

    habit_id: Mapped[str] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(nullable=False, index=True)
