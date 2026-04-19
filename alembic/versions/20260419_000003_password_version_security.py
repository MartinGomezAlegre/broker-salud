"""password version security

Revision ID: 20260419_000003
Revises: 20260418_000002
Create Date: 2026-04-19 00:00:03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_000003"
down_revision = "20260418_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS password_version INT NOT NULL DEFAULT 1
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE usuarios
            SET password_version = 1
            WHERE password_version IS NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE usuarios
            DROP COLUMN IF EXISTS password_version
            """
        )
    )
