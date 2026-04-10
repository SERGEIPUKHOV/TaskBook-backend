from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlannerLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planner_links"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_kind",
            "source_ref",
            "link_mode",
            name="uq_planner_links_user_source_ref_mode",
        ),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    link_mode: Mapped[str] = mapped_column(String(20), default="import_copy", nullable=False)
