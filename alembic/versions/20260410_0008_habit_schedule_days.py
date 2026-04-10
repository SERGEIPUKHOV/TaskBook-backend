"""habit schedule days

Revision ID: 20260410_0008
Revises: 20260409_0007
Create Date: 2026-04-10 15:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260410_0008"
down_revision = "20260409_0007"
branch_labels = None
depends_on = None


def _schedule_days_column_type(dialect_name: str) -> sa.types.TypeEngine[object]:
    if dialect_name == "sqlite":
        return sa.JSON()
    return postgresql.ARRAY(sa.Integer())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    habit_columns = {column["name"] for column in inspector.get_columns("habits")}

    if "schedule_days" not in habit_columns:
        op.add_column(
            "habits",
            sa.Column(
                "schedule_days",
                _schedule_days_column_type(bind.dialect.name),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    habit_columns = {column["name"] for column in inspector.get_columns("habits")}

    if "schedule_days" in habit_columns:
        op.drop_column("habits", "schedule_days")
