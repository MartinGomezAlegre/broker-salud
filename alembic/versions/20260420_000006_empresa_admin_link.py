"""empresa admin link

Revision ID: 20260420_000006
Revises: 20260419_000005
Create Date: 2026-04-20 00:00:06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_000006"
down_revision = "20260419_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE empresas
            ADD COLUMN IF NOT EXISTS admin_user_id INT REFERENCES usuarios(id) ON DELETE SET NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_empresas_admin_user_id
            ON empresas(admin_user_id)
            WHERE admin_user_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_empresas_admin_user_id"))
    op.execute(sa.text("ALTER TABLE empresas DROP COLUMN IF EXISTS admin_user_id"))
