"""audit log

Revision ID: 20260419_000004
Revises: 20260419_000003
Create Date: 2026-04-19 00:00:04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_000004"
down_revision = "20260419_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                actor_user_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
                action VARCHAR(120) NOT NULL,
                entity_type VARCHAR(120) NOT NULL,
                entity_id VARCHAR(120),
                ip_address VARCHAR(64),
                user_agent TEXT,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )

    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_audit_log_actor_user_id ON audit_log(actor_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at)",
    ):
        op.execute(sa.text(statement))


def downgrade() -> None:
    for statement in (
        "DROP INDEX IF EXISTS idx_audit_log_created_at",
        "DROP INDEX IF EXISTS idx_audit_log_entity",
        "DROP INDEX IF EXISTS idx_audit_log_action",
        "DROP INDEX IF EXISTS idx_audit_log_actor_user_id",
    ):
        op.execute(sa.text(statement))

    op.execute(sa.text("DROP TABLE IF EXISTS audit_log"))
