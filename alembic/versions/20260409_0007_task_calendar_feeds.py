"""task calendar feed export fields

Revision ID: 20260409_0007
Revises: 20260409_0006
Create Date: 2026-04-09 12:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_0007"
down_revision = "20260409_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "calendar_export_enabled" not in task_columns:
        op.add_column(
            "tasks",
            sa.Column("calendar_export_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "calendar_export_bucket" not in task_columns:
        op.add_column("tasks", sa.Column("calendar_export_bucket", sa.String(length=32), nullable=True))

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    user_indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "task_feed_token" not in user_columns:
        op.add_column("users", sa.Column("task_feed_token", sa.String(length=255), nullable=True))
    if "ix_users_task_feed_token" not in user_indexes:
        op.create_index("ix_users_task_feed_token", "users", ["task_feed_token"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    user_indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_task_feed_token" in user_indexes:
        op.drop_index("ix_users_task_feed_token", table_name="users")
    if "task_feed_token" in user_columns:
        op.drop_column("users", "task_feed_token")

    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "calendar_export_bucket" in task_columns:
        op.drop_column("tasks", "calendar_export_bucket")
    if "calendar_export_enabled" in task_columns:
        op.drop_column("tasks", "calendar_export_enabled")
