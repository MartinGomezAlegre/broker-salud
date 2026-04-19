"""account invitations

Revision ID: 20260419_000005
Revises: 20260419_000004
Create Date: 2026-04-19 00:00:05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_000005"
down_revision = "20260419_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS account_invitations (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                email VARCHAR(180) NOT NULL,
                role VARCHAR(50) NOT NULL,
                full_name VARCHAR(180) NOT NULL,
                token VARCHAR(120) NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                accepted_at TIMESTAMP,
                invited_by_user_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
                context_type VARCHAR(80),
                context_id VARCHAR(80),
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )

    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_account_invitations_user_id ON account_invitations(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_account_invitations_email ON account_invitations(email)",
        "CREATE INDEX IF NOT EXISTS idx_account_invitations_expires_at ON account_invitations(expires_at)",
    ):
        op.execute(sa.text(statement))


def downgrade() -> None:
    for statement in (
        "DROP INDEX IF EXISTS idx_account_invitations_expires_at",
        "DROP INDEX IF EXISTS idx_account_invitations_email",
        "DROP INDEX IF EXISTS idx_account_invitations_user_id",
    ):
        op.execute(sa.text(statement))

    op.execute(sa.text("DROP TABLE IF EXISTS account_invitations"))
