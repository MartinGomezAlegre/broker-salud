"""internal staff profiles

Revision ID: 20260422_000009
Revises: 20260422_000008
Create Date: 2026-04-22 00:00:09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260422_000009"
down_revision = "20260422_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personal_interno",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("area", sa.String(length=120), nullable=True),
        sa.Column("cargo", sa.String(length=120), nullable=True),
        sa.Column("responsabilidades", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_personal_interno_usuario_id", "personal_interno", ["usuario_id"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_personal_interno_usuario_id", table_name="personal_interno")
    op.drop_table("personal_interno")
