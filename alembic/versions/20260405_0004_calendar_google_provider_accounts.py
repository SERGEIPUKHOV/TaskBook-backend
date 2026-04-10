"""calendar google provider accounts

Revision ID: 20260405_0004
Revises: 20260405_0003
Create Date: 2026-04-05 22:00:00
"""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "20260405_0004"
down_revision = "20260405_0003"
branch_labels = None
depends_on = None


calendar_connections = sa.table(
    "calendar_connections",
    sa.column("id", sa.String()),
    sa.column("user_id", sa.String()),
    sa.column("provider", sa.String()),
    sa.column("status", sa.String()),
    sa.column("external_account_id", sa.String()),
    sa.column("account_label", sa.String()),
    sa.column("access_token_encrypted", sa.Text()),
    sa.column("refresh_token_encrypted", sa.Text()),
    sa.column("token_expires_at", sa.DateTime(timezone=True)),
    sa.column("last_synced_at", sa.DateTime(timezone=True)),
    sa.column("last_error", sa.Text()),
    sa.column("provider_account_id", sa.String()),
)

calendar_provider_accounts = sa.table(
    "calendar_provider_accounts",
    sa.column("id", sa.String()),
    sa.column("user_id", sa.String()),
    sa.column("provider", sa.String()),
    sa.column("status", sa.String()),
    sa.column("external_account_id", sa.String()),
    sa.column("account_label", sa.String()),
    sa.column("access_token_encrypted", sa.Text()),
    sa.column("refresh_token_encrypted", sa.Text()),
    sa.column("token_expires_at", sa.DateTime(timezone=True)),
    sa.column("last_synced_at", sa.DateTime(timezone=True)),
    sa.column("last_error", sa.Text()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        "calendar_provider_accounts",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=True),
        sa.Column("account_label", sa.String(length=255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
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
            name="uq_calendar_provider_accounts_user_provider",
        ),
    )
    op.create_index("ix_calendar_provider_accounts_user_id", "calendar_provider_accounts", ["user_id"], unique=False)
    op.create_index(
        "idx_calendar_provider_accounts_user_provider_status",
        "calendar_provider_accounts",
        ["user_id", "provider", "status"],
        unique=False,
    )

    op.add_column(
        "calendar_connections",
        sa.Column("provider_account_id", sa.Uuid(as_uuid=False), nullable=True),
    )
    op.create_index("ix_calendar_connections_provider_account_id", "calendar_connections", ["provider_account_id"], unique=False)
    op.create_foreign_key(
        "fk_calendar_connections_provider_account_id",
        "calendar_connections",
        "calendar_provider_accounts",
        ["provider_account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    bind = op.get_bind()
    google_rows = bind.execute(
        sa.select(
            calendar_connections.c.id,
            calendar_connections.c.user_id,
            calendar_connections.c.provider,
            calendar_connections.c.status,
            calendar_connections.c.external_account_id,
            calendar_connections.c.account_label,
            calendar_connections.c.access_token_encrypted,
            calendar_connections.c.refresh_token_encrypted,
            calendar_connections.c.token_expires_at,
            calendar_connections.c.last_synced_at,
            calendar_connections.c.last_error,
        ).where(calendar_connections.c.provider == "google"),
    ).mappings()

    for row in google_rows:
        provider_account_id = str(uuid4())
        bind.execute(
            calendar_provider_accounts.insert().values(
                id=provider_account_id,
                user_id=row["user_id"],
                provider="google",
                status=row["status"] or "active",
                external_account_id=row["external_account_id"],
                account_label=row["account_label"],
                access_token_encrypted=row["access_token_encrypted"],
                refresh_token_encrypted=row["refresh_token_encrypted"],
                token_expires_at=row["token_expires_at"],
                last_synced_at=row["last_synced_at"],
                last_error=row["last_error"],
            ),
        )
        bind.execute(
            calendar_connections.update()
            .where(calendar_connections.c.id == row["id"])
            .values(
                provider_account_id=provider_account_id,
                access_token_encrypted=None,
                refresh_token_encrypted=None,
                token_expires_at=None,
            ),
        )


def downgrade() -> None:
    op.drop_constraint("fk_calendar_connections_provider_account_id", "calendar_connections", type_="foreignkey")
    op.drop_index("ix_calendar_connections_provider_account_id", table_name="calendar_connections")
    op.drop_column("calendar_connections", "provider_account_id")

    op.drop_index("idx_calendar_provider_accounts_user_provider_status", table_name="calendar_provider_accounts")
    op.drop_index("ix_calendar_provider_accounts_user_id", table_name="calendar_provider_accounts")
    op.drop_table("calendar_provider_accounts")
