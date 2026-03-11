from __future__ import annotations

from datetime import date

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DailyState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_states"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_states_user_date"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(nullable=False, index=True)
    health: Mapped[int] = mapped_column(Integer, nullable=False)
    productivity: Mapped[int] = mapped_column(Integer, nullable=False)
    anxiety: Mapped[int] = mapped_column(Integer, nullable=False)
