"""baseline current state

Revision ID: 20260418_000001
Revises:
Create Date: 2026-04-18 00:00:01
"""
from __future__ import annotations


revision = "20260418_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Esta revision representa el schema actual existente.
    # En bases ya inicializadas se debe aplicar con:
    # alembic stamp 20260418_000001
    pass


def downgrade() -> None:
    pass
