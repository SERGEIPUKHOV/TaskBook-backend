from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TrackerGoal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tracker_goals"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    sprint_id: Mapped[str] = mapped_column(
        ForeignKey("tracker_sprints.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("tracker_goals.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline_date: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
