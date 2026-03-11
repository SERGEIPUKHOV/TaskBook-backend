"""initial schema

Revision ID: 20260310_0001
Revises:
Create Date: 2026-03-10 14:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260310_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("reset_token", sa.String(length=255), nullable=True),
        sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_reset_token", "users", ["reset_token"], unique=False)

    op.create_table(
        "daily_states",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("health", sa.Integer(), nullable=False),
        sa.Column("productivity", sa.Integer(), nullable=False),
        sa.Column("anxiety", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "date", name="uq_daily_states_user_date"),
    )
    op.create_index("ix_daily_states_date", "daily_states", ["date"], unique=False)
    op.create_index("ix_daily_states_user_id", "daily_states", ["user_id"], unique=False)

    op.create_table(
        "gratitudes",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gratitudes_date", "gratitudes", ["date"], unique=False)
    op.create_index("ix_gratitudes_user_id", "gratitudes", ["user_id"], unique=False)

    op.create_table(
        "habits",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("starts_at_month_key", sa.String(length=7), nullable=True),
        sa.Column("ends_before_month_key", sa.String(length=7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_habits_ends_before_month_key", "habits", ["ends_before_month_key"], unique=False)
    op.create_index("ix_habits_starts_at_month_key", "habits", ["starts_at_month_key"], unique=False)
    op.create_index("ix_habits_user_id", "habits", ["user_id"], unique=False)

    op.create_table(
        "key_events",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_key_events_date", "key_events", ["date"], unique=False)
    op.create_index("ix_key_events_user_id", "key_events", ["user_id"], unique=False)

    op.create_table(
        "month_plans",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("main_goal", sa.Text(), nullable=True),
        sa.Column("focuses", sa.JSON(), nullable=False),
        sa.Column("innovations", sa.JSON(), nullable=False),
        sa.Column("rejections", sa.JSON(), nullable=False),
        sa.Column("other", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year", "month", name="uq_month_plans_user_period"),
    )
    op.create_index("ix_month_plans_user_id", "month_plans", ["user_id"], unique=False)

    op.create_table(
        "weeks",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("focus", sa.Text(), nullable=True),
        sa.Column("reward", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year", "week_number", name="uq_weeks_user_period"),
    )
    op.create_index("ix_weeks_user_id", "weeks", ["user_id"], unique=False)

    op.create_table(
        "habit_logs",
        sa.Column("habit_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["habit_id"], ["habits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("habit_id", "date", name="uq_habit_logs_habit_date"),
    )
    op.create_index("ix_habit_logs_date", "habit_logs", ["date"], unique=False)
    op.create_index("ix_habit_logs_habit_id", "habit_logs", ["habit_id"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("week_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("time_planned", sa.Integer(), nullable=True),
        sa.Column("time_actual", sa.Integer(), nullable=True),
        sa.Column("is_priority", sa.Boolean(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("start_day", sa.Integer(), nullable=True),
        sa.Column("carried_from_task_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["carried_from_task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["week_id"], ["weeks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"], unique=False)
    op.create_index("ix_tasks_week_id", "tasks", ["week_id"], unique=False)

    op.create_table(
        "task_day_statuses",
        sa.Column("task_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "date", name="uq_task_day_status_task_date"),
    )
    op.create_index("ix_task_day_statuses_date", "task_day_statuses", ["date"], unique=False)
    op.create_index("ix_task_day_statuses_task_id", "task_day_statuses", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_day_statuses_task_id", table_name="task_day_statuses")
    op.drop_index("ix_task_day_statuses_date", table_name="task_day_statuses")
    op.drop_table("task_day_statuses")

    op.drop_index("ix_tasks_week_id", table_name="tasks")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_habit_logs_habit_id", table_name="habit_logs")
    op.drop_index("ix_habit_logs_date", table_name="habit_logs")
    op.drop_table("habit_logs")

    op.drop_index("ix_weeks_user_id", table_name="weeks")
    op.drop_table("weeks")

    op.drop_index("ix_month_plans_user_id", table_name="month_plans")
    op.drop_table("month_plans")

    op.drop_index("ix_key_events_user_id", table_name="key_events")
    op.drop_index("ix_key_events_date", table_name="key_events")
    op.drop_table("key_events")

    op.drop_index("ix_habits_user_id", table_name="habits")
    op.drop_index("ix_habits_starts_at_month_key", table_name="habits")
    op.drop_index("ix_habits_ends_before_month_key", table_name="habits")
    op.drop_table("habits")

    op.drop_index("ix_gratitudes_user_id", table_name="gratitudes")
    op.drop_index("ix_gratitudes_date", table_name="gratitudes")
    op.drop_table("gratitudes")

    op.drop_index("ix_daily_states_user_id", table_name="daily_states")
    op.drop_index("ix_daily_states_date", table_name="daily_states")
    op.drop_table("daily_states")

    op.drop_index("ix_users_reset_token", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
