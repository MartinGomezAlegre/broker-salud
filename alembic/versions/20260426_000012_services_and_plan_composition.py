"""services and plan composition

Revision ID: 20260426_000012
Revises: 20260422_000011
Create Date: 2026-04-26 00:00:12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260426_000012"
down_revision = "20260422_000011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("nombre", sa.String(length=140), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("proveedor", sa.String(length=80), nullable=False),
        sa.Column("access_mode", sa.String(length=40), nullable=True),
        sa.Column("access_instructions", sa.Text(), nullable=True),
        sa.Column("cta_label", sa.String(length=120), nullable=True),
        sa.Column("cta_url", sa.String(length=400), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("orden_display", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("code", name="uq_services_code"),
    )
    op.create_index("idx_services_activo", "services", ["activo"], unique=False)
    op.create_index("idx_services_orden_display", "services", ["orden_display"], unique=False)

    op.create_table(
        "plan_services",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("planes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("plan_id", "service_id", name="uq_plan_services_plan_service"),
    )
    op.create_index("idx_plan_services_plan_id", "plan_services", ["plan_id"], unique=False)
    op.create_index("idx_plan_services_service_id", "plan_services", ["service_id"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO services
                (code, nombre, descripcion, proveedor, access_mode, access_instructions, cta_label, cta_url, orden_display)
            VALUES
                (
                    'mediquo_telemedicina',
                    'Telemedicina',
                    'Consultas online, recetas digitales y seguimiento medico desde la plataforma.',
                    'Mediquo',
                    'external_link',
                    'Accede a Mediquo desde tu cuenta CelDoctor para iniciar videoconsultas, recetas y seguimiento clinico.',
                    'Abrir Mediquo',
                    'https://mediquo.com',
                    10
                ),
                (
                    'cardinal_chequeo_anual',
                    'Chequeo anual',
                    '1 evento por año. Incluye electrocardiograma, analisis de sangre y orina, ecografia abdominal y PAP.',
                    'Cardinal Assistance',
                    'coordination',
                    'Solicita la coordinacion del chequeo anual desde CelDoctor o por los canales informados por Cardinal Assistance.',
                    'Ver condiciones',
                    NULL,
                    20
                ),
                (
                    'cardinal_odontologia_urgencia',
                    'Odontologia de urgencia',
                    'Hasta 6 eventos por año. Tope de hasta ARS 80.000 por evento.',
                    'Cardinal Assistance',
                    'coordination',
                    'Accede al servicio de odontologia de urgencia con coordinacion previa por Cardinal Assistance.',
                    'Ver condiciones',
                    NULL,
                    30
                ),
                (
                    'cardinal_descuentos_medicamentos',
                    'Descuentos en medicamentos',
                    'Hasta 6 eventos por año. Tope de hasta ARS 80.000 por evento y hasta 40% de descuento.',
                    'Cardinal Assistance',
                    'coordination',
                    'Consulta en plataforma o con Cardinal Assistance como aplicar el beneficio en medicamentos adheridos.',
                    'Ver condiciones',
                    NULL,
                    40
                ),
                (
                    'cardinal_descuentos_farmacias',
                    'Descuentos en farmacias',
                    'Beneficio general disponible en farmacias adheridas.',
                    'Cardinal Assistance',
                    'information',
                    'Revisa las farmacias adheridas y las condiciones del beneficio desde tu cuenta CelDoctor.',
                    'Ver condiciones',
                    NULL,
                    50
                )
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO plan_services (plan_id, service_id)
            SELECT p.id, s.id
            FROM planes p
            CROSS JOIN services s
            WHERE NOT EXISTS (
                SELECT 1
                FROM plan_services ps
                WHERE ps.plan_id = p.id
                  AND ps.service_id = s.id
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_plan_services_service_id", table_name="plan_services")
    op.drop_index("idx_plan_services_plan_id", table_name="plan_services")
    op.drop_table("plan_services")

    op.drop_index("idx_services_orden_display", table_name="services")
    op.drop_index("idx_services_activo", table_name="services")
    op.drop_table("services")
