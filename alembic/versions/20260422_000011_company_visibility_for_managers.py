"""company visibility for managers

Revision ID: 20260422_000011
Revises: 20260422_000010
Create Date: 2026-04-22 00:00:11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260422_000011"
down_revision = "20260422_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "empresas",
        sa.Column("visible_para_gestores", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("empresas", "visible_para_gestores")
