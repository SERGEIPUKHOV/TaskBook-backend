from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    week_id: Mapped[str] = mapped_column(ForeignKey("weeks.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    time_planned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    carried_from_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )


class TaskDayStatus(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "task_day_statuses"
    __table_args__ = (UniqueConstraint("task_id", "date", name="uq_task_day_status_task_date"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
