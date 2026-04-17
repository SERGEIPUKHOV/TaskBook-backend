"""tasktracker

Revision ID: 20260417_0010
Revises: 20260416_0009
Create Date: 2026-04-17 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_0010"
down_revision = "20260416_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    user_columns = {column["name"] for column in inspector.get_columns("users")}

    if "tasktracker_enabled" not in user_columns:
        op.add_column(
            "users",
            sa.Column("tasktracker_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    if "tracker_sprints" not in tables:
        op.create_table(
            "tracker_sprints",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_tracker_sprints_user_id", "tracker_sprints", ["user_id"])

    if "tracker_goals" not in tables:
        op.create_table(
            "tracker_goals",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sprint_id", sa.Uuid(as_uuid=False), sa.ForeignKey("tracker_sprints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section", sa.String(length=32), nullable=False),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column("parent_id", sa.Uuid(as_uuid=False), sa.ForeignKey("tracker_goals.id", ondelete="CASCADE"), nullable=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("hypothesis", sa.Text(), nullable=True),
            sa.Column("deadline_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_tracker_goals_sprint_id", "tracker_goals", ["sprint_id"])
        op.create_index("ix_tracker_goals_user_id", "tracker_goals", ["user_id"])
        op.create_index("ix_tracker_goals_parent_id", "tracker_goals", ["parent_id"])
        op.create_index("ix_tracker_goals_deadline_date", "tracker_goals", ["deadline_date"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "tracker_goals" in tables:
        op.drop_index("ix_tracker_goals_deadline_date", table_name="tracker_goals")
        op.drop_index("ix_tracker_goals_parent_id", table_name="tracker_goals")
        op.drop_index("ix_tracker_goals_user_id", table_name="tracker_goals")
        op.drop_index("ix_tracker_goals_sprint_id", table_name="tracker_goals")
        op.drop_table("tracker_goals")

    if "tracker_sprints" in tables:
        op.drop_index("ix_tracker_sprints_user_id", table_name="tracker_sprints")
        op.drop_table("tracker_sprints")

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "tasktracker_enabled" in user_columns:
        op.drop_column("users", "tasktracker_enabled")
