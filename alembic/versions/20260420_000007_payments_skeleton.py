"""payments skeleton

Revision ID: 20260420_000007
Revises: 20260420_000006
Create Date: 2026-04-20 20:05:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260420_000007"
down_revision = "20260420_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intentos_pago",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("suscripcion_id", sa.Integer(), sa.ForeignKey("suscripciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proveedor", sa.Text(), nullable=False),
        sa.Column("external_reference", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("moneda", sa.Text(), nullable=False, server_default="ARS"),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("payment_id", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_intentos_pago_suscripcion_id", "intentos_pago", ["suscripcion_id"])
    op.create_index("ix_intentos_pago_usuario_id", "intentos_pago", ["usuario_id"])
    op.create_index("ux_intentos_pago_external_reference", "intentos_pago", ["external_reference"], unique=True)

    op.create_table(
        "webhooks_recibidos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proveedor", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=True),
        sa.Column("payment_id", sa.Text(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("firma_valida", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_webhooks_recibidos_payment_id", "webhooks_recibidos", ["payment_id"])
    op.create_index("ix_webhooks_recibidos_proveedor", "webhooks_recibidos", ["proveedor"])

    op.create_table(
        "pagos_procesados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proveedor", sa.Text(), nullable=False),
        sa.Column("payment_id", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("suscripcion_id", sa.Integer(), sa.ForeignKey("suscripciones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pago_id", sa.Integer(), sa.ForeignKey("pagos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("webhook_id", sa.Integer(), sa.ForeignKey("webhooks_recibidos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("monto", sa.Numeric(10, 2), nullable=True),
        sa.Column("moneda", sa.Text(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ux_pagos_procesados_provider_payment",
        "pagos_procesados",
        ["proveedor", "payment_id"],
        unique=True,
    )
    op.create_index("ix_pagos_procesados_suscripcion_id", "pagos_procesados", ["suscripcion_id"])


def downgrade() -> None:
    op.drop_index("ix_pagos_procesados_suscripcion_id", table_name="pagos_procesados")
    op.drop_index("ux_pagos_procesados_provider_payment", table_name="pagos_procesados")
    op.drop_table("pagos_procesados")

    op.drop_index("ix_webhooks_recibidos_proveedor", table_name="webhooks_recibidos")
    op.drop_index("ix_webhooks_recibidos_payment_id", table_name="webhooks_recibidos")
    op.drop_table("webhooks_recibidos")

    op.drop_index("ux_intentos_pago_external_reference", table_name="intentos_pago")
    op.drop_index("ix_intentos_pago_usuario_id", table_name="intentos_pago")
    op.drop_index("ix_intentos_pago_suscripcion_id", table_name="intentos_pago")
    op.drop_table("intentos_pago")
