"""calendar connections and events

Revision ID: 20260405_0003
Revises: 20260311_0002
Create Date: 2026-04-05 18:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260405_0003"
down_revision = "20260311_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_connections",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=False),
        sa.Column("account_label", sa.String(length=255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_cursor", sa.Text(), nullable=True),
        sa.Column("ics_url_encrypted", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "external_account_id",
            name="uq_calendar_connections_user_provider_account",
        ),
    )
    op.create_index("ix_calendar_connections_user_id", "calendar_connections", ["user_id"], unique=False)
    op.create_index(
        "idx_calendar_connections_user_provider_status",
        "calendar_connections",
        ["user_id", "provider", "status"],
        unique=False,
    )

    op.create_table(
        "calendar_events",
        sa.Column("connection_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("external_calendar_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_timezone", sa.String(length=100), nullable=True),
        sa.Column("is_all_day", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["calendar_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_id",
            "external_event_id",
            name="uq_calendar_events_connection_external_event",
        ),
    )
    op.create_index("ix_calendar_events_connection_id", "calendar_events", ["connection_id"], unique=False)
    op.create_index("ix_calendar_events_starts_at", "calendar_events", ["starts_at"], unique=False)
    op.create_index("ix_calendar_events_user_id", "calendar_events", ["user_id"], unique=False)
    op.create_index(
        "idx_calendar_events_user_starts_at",
        "calendar_events",
        ["user_id", "starts_at"],
        unique=False,
    )
    op.create_index(
        "idx_calendar_events_connection_starts_at",
        "calendar_events",
        ["connection_id", "starts_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_calendar_events_connection_starts_at", table_name="calendar_events")
    op.drop_index("idx_calendar_events_user_starts_at", table_name="calendar_events")
    op.drop_index("ix_calendar_events_user_id", table_name="calendar_events")
    op.drop_index("ix_calendar_events_starts_at", table_name="calendar_events")
    op.drop_index("ix_calendar_events_connection_id", table_name="calendar_events")
    op.drop_table("calendar_events")

    op.drop_index("idx_calendar_connections_user_provider_status", table_name="calendar_connections")
    op.drop_index("ix_calendar_connections_user_id", table_name="calendar_connections")
    op.drop_table("calendar_connections")
