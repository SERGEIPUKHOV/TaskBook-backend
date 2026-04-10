"""planner links for calendar bridge

Revision ID: 20260409_0006
Revises: 20260406_0005
Create Date: 2026-04-09 02:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_0006"
down_revision = "20260406_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "planner_links" in existing_tables:
        return

    op.create_table(
        "planner_links",
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=512), nullable=False),
        sa.Column("target_kind", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("link_mode", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "source_kind",
            "source_ref",
            "link_mode",
            name="uq_planner_links_user_source_ref_mode",
        ),
    )
    op.create_index("ix_planner_links_user_id", "planner_links", ["user_id"], unique=False)
    op.create_index("ix_planner_links_source_ref", "planner_links", ["source_ref"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "planner_links" not in existing_tables:
        return

    op.drop_index("ix_planner_links_source_ref", table_name="planner_links")
    op.drop_index("ix_planner_links_user_id", table_name="planner_links")
    op.drop_table("planner_links")
