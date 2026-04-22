"""company agreements

Revision ID: 20260422_000008
Revises: 20260420_000007
Create Date: 2026-04-22 00:00:08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260422_000008"
down_revision = "20260420_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "empresa_acuerdos",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=50), nullable=False, server_default="vigente"),
        sa.Column("fecha_firma", sa.Date(), nullable=True),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=True),
        sa.Column("archivo_url", sa.Text(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_empresa_acuerdos_empresa_id", "empresa_acuerdos", ["empresa_id"])
    op.create_index("idx_empresa_acuerdos_estado", "empresa_acuerdos", ["estado"])


def downgrade() -> None:
    op.drop_index("idx_empresa_acuerdos_estado", table_name="empresa_acuerdos")
    op.drop_index("idx_empresa_acuerdos_empresa_id", table_name="empresa_acuerdos")
    op.drop_table("empresa_acuerdos")
