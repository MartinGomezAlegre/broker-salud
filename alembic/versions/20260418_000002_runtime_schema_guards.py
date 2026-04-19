"""runtime schema guards

Revision ID: 20260418_000002
Revises: 20260418_000001
Create Date: 2026-04-18 00:00:02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260418_000002"
down_revision = "20260418_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE suscripciones
                ADD COLUMN IF NOT EXISTS fecha_vencimiento DATE,
                ADD COLUMN IF NOT EXISTS referral_code VARCHAR(40),
                ADD COLUMN IF NOT EXISTS broker_seller_id INT,
                ADD COLUMN IF NOT EXISTS direct_seller_id INT
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS brokers (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(120) NOT NULL,
                contacto VARCHAR(160),
                comision_tipo VARCHAR(20) NOT NULL CHECK (comision_tipo IN ('porcentaje', 'fijo')),
                comision_valor NUMERIC(12,2) NOT NULL CHECK (comision_valor > 0),
                estado VARCHAR(20) NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
                fecha_alta TIMESTAMP NOT NULL DEFAULT NOW(),
                usuario_id INT REFERENCES usuarios(id) ON DELETE SET NULL
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS broker_sellers (
                id SERIAL PRIMARY KEY,
                broker_id INT NOT NULL REFERENCES brokers(id) ON DELETE CASCADE,
                nombre VARCHAR(120) NOT NULL,
                email VARCHAR(180) NOT NULL,
                referral_code VARCHAR(40) NOT NULL UNIQUE,
                estado VARCHAR(20) NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
                fecha_alta TIMESTAMP NOT NULL DEFAULT NOW(),
                usuario_id INT REFERENCES usuarios(id) ON DELETE SET NULL
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS direct_sellers (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(120) NOT NULL,
                email VARCHAR(180) NOT NULL,
                referral_code VARCHAR(40) NOT NULL UNIQUE,
                comision_tipo VARCHAR(20) NOT NULL CHECK (comision_tipo IN ('porcentaje', 'fijo')),
                comision_valor NUMERIC(12,2) NOT NULL CHECK (comision_valor > 0),
                estado VARCHAR(20) NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo')),
                fecha_alta TIMESTAMP NOT NULL DEFAULT NOW(),
                usuario_id INT REFERENCES usuarios(id) ON DELETE SET NULL
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS commission_liquidations (
                id SERIAL PRIMARY KEY,
                destinatario_tipo VARCHAR(20) NOT NULL CHECK (destinatario_tipo IN ('broker', 'direct_seller')),
                destinatario_id INT NOT NULL,
                monto NUMERIC(12,2) NOT NULL CHECK (monto > 0),
                periodo_desde DATE,
                periodo_hasta DATE,
                estado VARCHAR(20) NOT NULL DEFAULT 'pagada',
                notas TEXT,
                paid_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                admin_id INT REFERENCES usuarios(id) ON DELETE SET NULL
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS qr_validations (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
                benefit_type VARCHAR(50) NOT NULL DEFAULT 'farmacia',
                validation_status VARCHAR(20) NOT NULL,
                source_ip VARCHAR(64),
                user_agent TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS upsells_seguro (
                id SERIAL PRIMARY KEY,
                usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                suscripcion_id INT NOT NULL REFERENCES suscripciones(id) ON DELETE CASCADE,
                plan_nombre VARCHAR(120) NOT NULL,
                precio_ofertado NUMERIC(12,2) NOT NULL,
                estado VARCHAR(20) NOT NULL DEFAULT 'nuevo',
                nota_admin TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'suscripciones_broker_seller_id_fkey'
                ) THEN
                    ALTER TABLE suscripciones
                        ADD CONSTRAINT suscripciones_broker_seller_id_fkey
                        FOREIGN KEY (broker_seller_id)
                        REFERENCES broker_sellers(id)
                        ON DELETE SET NULL;
                END IF;
            END $$;
            """
        )
    )

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'suscripciones_direct_seller_id_fkey'
                ) THEN
                    ALTER TABLE suscripciones
                        ADD CONSTRAINT suscripciones_direct_seller_id_fkey
                        FOREIGN KEY (direct_seller_id)
                        REFERENCES direct_sellers(id)
                        ON DELETE SET NULL;
                END IF;
            END $$;
            """
        )
    )

    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_brokers_estado ON brokers(estado)",
        "CREATE INDEX IF NOT EXISTS idx_brokers_usuario_id ON brokers(usuario_id)",
        "CREATE INDEX IF NOT EXISTS idx_broker_sellers_broker_id ON broker_sellers(broker_id)",
        "CREATE INDEX IF NOT EXISTS idx_broker_sellers_estado ON broker_sellers(estado)",
        "CREATE INDEX IF NOT EXISTS idx_broker_sellers_usuario_id ON broker_sellers(usuario_id)",
        "CREATE INDEX IF NOT EXISTS idx_direct_sellers_estado ON direct_sellers(estado)",
        "CREATE INDEX IF NOT EXISTS idx_direct_sellers_usuario_id ON direct_sellers(usuario_id)",
        "CREATE INDEX IF NOT EXISTS idx_suscripciones_referral_code ON suscripciones(referral_code)",
        "CREATE INDEX IF NOT EXISTS idx_suscripciones_broker_seller_id ON suscripciones(broker_seller_id)",
        "CREATE INDEX IF NOT EXISTS idx_suscripciones_direct_seller_id ON suscripciones(direct_seller_id)",
        "CREATE INDEX IF NOT EXISTS idx_commission_liquidations_destinatario ON commission_liquidations(destinatario_tipo, destinatario_id)",
        "CREATE INDEX IF NOT EXISTS idx_commission_liquidations_paid_at ON commission_liquidations(paid_at)",
        "CREATE INDEX IF NOT EXISTS idx_qr_validations_user_id ON qr_validations(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_qr_validations_created_at ON qr_validations(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_upsells_seguro_usuario_id ON upsells_seguro(usuario_id)",
        "CREATE INDEX IF NOT EXISTS idx_upsells_seguro_suscripcion_id ON upsells_seguro(suscripcion_id)",
        "CREATE INDEX IF NOT EXISTS idx_upsells_seguro_estado ON upsells_seguro(estado)",
    ):
        op.execute(sa.text(statement))


def downgrade() -> None:
    for statement in (
        "DROP INDEX IF EXISTS idx_upsells_seguro_estado",
        "DROP INDEX IF EXISTS idx_upsells_seguro_suscripcion_id",
        "DROP INDEX IF EXISTS idx_upsells_seguro_usuario_id",
        "DROP INDEX IF EXISTS idx_qr_validations_created_at",
        "DROP INDEX IF EXISTS idx_qr_validations_user_id",
        "DROP INDEX IF EXISTS idx_commission_liquidations_paid_at",
        "DROP INDEX IF EXISTS idx_commission_liquidations_destinatario",
        "DROP INDEX IF EXISTS idx_suscripciones_direct_seller_id",
        "DROP INDEX IF EXISTS idx_suscripciones_broker_seller_id",
        "DROP INDEX IF EXISTS idx_suscripciones_referral_code",
        "DROP INDEX IF EXISTS idx_direct_sellers_usuario_id",
        "DROP INDEX IF EXISTS idx_direct_sellers_estado",
        "DROP INDEX IF EXISTS idx_broker_sellers_usuario_id",
        "DROP INDEX IF EXISTS idx_broker_sellers_estado",
        "DROP INDEX IF EXISTS idx_broker_sellers_broker_id",
        "DROP INDEX IF EXISTS idx_brokers_usuario_id",
        "DROP INDEX IF EXISTS idx_brokers_estado",
    ):
        op.execute(sa.text(statement))

    op.execute(
        sa.text(
            """
            ALTER TABLE suscripciones
                DROP CONSTRAINT IF EXISTS suscripciones_direct_seller_id_fkey,
                DROP CONSTRAINT IF EXISTS suscripciones_broker_seller_id_fkey,
                DROP COLUMN IF EXISTS direct_seller_id,
                DROP COLUMN IF EXISTS broker_seller_id,
                DROP COLUMN IF EXISTS referral_code,
                DROP COLUMN IF EXISTS fecha_vencimiento
            """
        )
    )

    for statement in (
        "DROP TABLE IF EXISTS upsells_seguro",
        "DROP TABLE IF EXISTS qr_validations",
        "DROP TABLE IF EXISTS commission_liquidations",
        "DROP TABLE IF EXISTS direct_sellers",
        "DROP TABLE IF EXISTS broker_sellers",
        "DROP TABLE IF EXISTS brokers",
    ):
        op.execute(sa.text(statement))
