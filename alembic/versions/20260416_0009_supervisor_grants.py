"""supervisor grants

Revision ID: 20260416_0009
Revises: 20260410_0008
Create Date: 2026-04-16 17:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260416_0009"
down_revision = "20260410_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "supervisor_grants" in tables:
        return

    op.create_table(
        "supervisor_grants",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supervisor_email", sa.String(length=255), nullable=False),
        sa.Column("supervisor_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sections", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supervisor_grants_owner_id", "supervisor_grants", ["owner_id"])
    op.create_index("ix_supervisor_grants_supervisor_email", "supervisor_grants", ["supervisor_email"])
    op.create_index("ix_supervisor_grants_supervisor_id", "supervisor_grants", ["supervisor_id"])
    op.create_index(
        "ix_supervisor_grants_owner_supervisor",
        "supervisor_grants",
        ["owner_id", "supervisor_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "supervisor_grants" not in tables:
        return

    op.drop_index("ix_supervisor_grants_owner_supervisor", table_name="supervisor_grants")
    op.drop_index("ix_supervisor_grants_supervisor_id", table_name="supervisor_grants")
    op.drop_index("ix_supervisor_grants_supervisor_email", table_name="supervisor_grants")
    op.drop_index("ix_supervisor_grants_owner_id", table_name="supervisor_grants")
    op.drop_table("supervisor_grants")
