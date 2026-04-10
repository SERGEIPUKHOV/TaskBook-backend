"""calendar connection colors

Revision ID: 20260406_0005
Revises: 20260405_0004
Create Date: 2026-04-06 02:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260406_0005"
down_revision = "20260405_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("calendar_connections")}

    if "color" not in existing_columns:
        op.add_column("calendar_connections", sa.Column("color", sa.String(length=7), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("calendar_connections")}

    if "color" in existing_columns:
        op.drop_column("calendar_connections", "color")
