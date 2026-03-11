"""production indexes

Revision ID: 20260311_0002
Revises: 20260310_0001
Create Date: 2026-03-11 19:30:00
"""

from __future__ import annotations

from alembic import op


revision = "20260311_0002"
down_revision = "20260310_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_gratitudes_user_date",
        "gratitudes",
        ["user_id", "date"],
        unique=False,
    )
    op.create_index(
        "idx_habits_user_month_window",
        "habits",
        ["user_id", "starts_at_month_key", "ends_before_month_key"],
        unique=False,
    )
    op.create_index(
        "idx_key_events_user_date",
        "key_events",
        ["user_id", "date"],
        unique=False,
    )
    op.create_index(
        "idx_tasks_user_week_carried_from",
        "tasks",
        ["user_id", "week_id", "carried_from_task_id"],
        unique=False,
    )
    op.create_index(
        "idx_tasks_week_order",
        "tasks",
        ["week_id", "order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_week_order", table_name="tasks")
    op.drop_index("idx_tasks_user_week_carried_from", table_name="tasks")
    op.drop_index("idx_key_events_user_date", table_name="key_events")
    op.drop_index("idx_habits_user_month_window", table_name="habits")
    op.drop_index("idx_gratitudes_user_date", table_name="gratitudes")
