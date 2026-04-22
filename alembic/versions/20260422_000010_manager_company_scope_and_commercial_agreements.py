"""manager company scope and commercial agreements

Revision ID: 20260422_000010
Revises: 20260422_000009
Create Date: 2026-04-22 00:00:10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260422_000010"
down_revision = "20260422_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gestor_empresas_permitidas",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("usuario_id", "empresa_id", name="uq_gestor_empresas_permitidas_usuario_empresa"),
    )
    op.create_index("idx_gestor_empresas_permitidas_usuario_id", "gestor_empresas_permitidas", ["usuario_id"], unique=False)
    op.create_index("idx_gestor_empresas_permitidas_empresa_id", "gestor_empresas_permitidas", ["empresa_id"], unique=False)

    op.create_table(
        "comercial_acuerdos",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("destinatario_tipo", sa.String(length=40), nullable=False),
        sa.Column("destinatario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=40), nullable=False, server_default="vigente"),
        sa.Column("fecha_firma", sa.Date(), nullable=True),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=True),
        sa.Column("archivo_url", sa.String(length=400), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index(
        "idx_comercial_acuerdos_destinatario",
        "comercial_acuerdos",
        ["destinatario_tipo", "destinatario_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_comercial_acuerdos_destinatario", table_name="comercial_acuerdos")
    op.drop_table("comercial_acuerdos")

    op.drop_index("idx_gestor_empresas_permitidas_empresa_id", table_name="gestor_empresas_permitidas")
    op.drop_index("idx_gestor_empresas_permitidas_usuario_id", table_name="gestor_empresas_permitidas")
    op.drop_table("gestor_empresas_permitidas")
