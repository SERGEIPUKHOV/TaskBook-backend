from __future__ import annotations

from datetime import date

from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SCHEDULE_DAYS_TYPE = ARRAY(Integer).with_variant(JSON, "sqlite")


class Habit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "habits"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    starts_at_month_key: Mapped[str | None] = mapped_column(String(7), index=True, nullable=True)
    ends_before_month_key: Mapped[str | None] = mapped_column(String(7), index=True, nullable=True)
    schedule_days: Mapped[list[int] | None] = mapped_column(SCHEDULE_DAYS_TYPE, nullable=True, default=None)


class HabitLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "habit_logs"
    __table_args__ = (UniqueConstraint("habit_id", "date", name="uq_habit_logs_habit_date"),)

    habit_id: Mapped[str] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(nullable=False, index=True)
