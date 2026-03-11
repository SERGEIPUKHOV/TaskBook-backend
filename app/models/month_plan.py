from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MonthPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "month_plans"
    __table_args__ = (UniqueConstraint("user_id", "year", "month", name="uq_month_plans_user_period"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    main_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    focuses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    innovations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    rejections: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    other: Mapped[str | None] = mapped_column(Text, nullable=True)
