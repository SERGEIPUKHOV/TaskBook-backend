"""tracker goal target fields

Revision ID: 20260417_0011
Revises: 20260417_0010
Create Date: 2026-04-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260417_0011"
down_revision = "20260417_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracker_goals", sa.Column("target_baseline", sa.Text(), nullable=True))
    op.add_column("tracker_goals", sa.Column("target_stretch", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tracker_goals", "target_stretch")
    op.drop_column("tracker_goals", "target_baseline")
