"""vademecum and pharmacies catalog

Revision ID: 20260426_000013
Revises: 20260426_000012
Create Date: 2026-04-26 00:00:13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260426_000013"
down_revision = "20260426_000012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vademecum_medicamentos",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("nombre", sa.String(length=160), nullable=False),
        sa.Column("principio_activo", sa.String(length=160), nullable=True),
        sa.Column("presentacion", sa.String(length=160), nullable=True),
        sa.Column("laboratorio", sa.String(length=160), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("cobertura_resumen", sa.String(length=240), nullable=True),
        sa.Column("descuento_porcentaje", sa.Integer(), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("orden_display", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_vademecum_medicamentos_activo", "vademecum_medicamentos", ["activo"], unique=False)
    op.create_index("idx_vademecum_medicamentos_orden", "vademecum_medicamentos", ["orden_display"], unique=False)

    op.create_table(
        "farmacias_adheridas",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("nombre", sa.String(length=180), nullable=False),
        sa.Column("direccion", sa.String(length=220), nullable=False),
        sa.Column("localidad", sa.String(length=120), nullable=True),
        sa.Column("provincia", sa.String(length=120), nullable=True),
        sa.Column("telefono", sa.String(length=80), nullable=True),
        sa.Column("horario", sa.String(length=180), nullable=True),
        sa.Column("estado_atencion", sa.String(length=80), nullable=True),
        sa.Column("distancia_km", sa.Numeric(10, 2), nullable=True),
        sa.Column("descuento_porcentaje", sa.Integer(), nullable=True),
        sa.Column("maps_url", sa.String(length=400), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("orden_display", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_farmacias_adheridas_activo", "farmacias_adheridas", ["activo"], unique=False)
    op.create_index("idx_farmacias_adheridas_orden", "farmacias_adheridas", ["orden_display"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO vademecum_medicamentos
                (nombre, principio_activo, presentacion, laboratorio, descripcion, cobertura_resumen, descuento_porcentaje, keywords, orden_display)
            VALUES
                ('Ibuprofeno 600', 'Ibuprofeno', '20 comprimidos', 'Generico', 'Analgesico y antiinflamatorio de uso frecuente.', 'Hasta 40% de descuento en farmacias adheridas.', 40, 'dolor fiebre antiinflamatorio ibuprofeno', 10),
                ('Paracetamol 1g', 'Paracetamol', '16 comprimidos', 'Generico', 'Analgasico y antipiretico para fiebre y dolor.', 'Hasta 40% de descuento en farmacias adheridas.', 40, 'fiebre dolor paracetamol acetaminofen', 20),
                ('Losartan 50', 'Losartan', '30 comprimidos', 'Generico', 'Tratamiento antihipertensivo de uso cronico.', 'Descuento disponible segun red adherida.', 25, 'presion hipertension losartan', 30),
                ('Omeprazol 20', 'Omeprazol', '30 capsulas', 'Generico', 'Protector gastrico de uso habitual.', 'Descuento disponible segun red adherida.', 25, 'gastrico acidez omeprazol', 40)
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO farmacias_adheridas
                (nombre, direccion, localidad, provincia, telefono, horario, estado_atencion, distancia_km, descuento_porcentaje, maps_url, descripcion, orden_display)
            VALUES
                ('Farmacity Centro', 'Av. Santa Fe 1234', 'CABA', 'Buenos Aires', '011-4321-0001', '24 hs', 'Abierta 24 hs', 0.3, 30, 'https://maps.google.com/?q=Av.+Santa+Fe+1234', 'Sucursal adherida con atencion extendida.', 10),
                ('FarmaPlus Norte', 'Av. Cordoba 5678', 'CABA', 'Buenos Aires', '011-4321-0002', '08:00 a 22:00', 'Abierta', 0.7, 25, 'https://maps.google.com/?q=Av.+Cordoba+5678', 'Farmacia adherida con descuentos en medicamentos seleccionados.', 20),
                ('Central Oeste', 'Av. Rivadavia 9100', 'CABA', 'Buenos Aires', '011-4321-0003', '09:00 a 20:00', 'Abierta', 1.2, 20, 'https://maps.google.com/?q=Av.+Rivadavia+9100', 'Beneficios generales en farmacia adherida.', 30)
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_farmacias_adheridas_orden", table_name="farmacias_adheridas")
    op.drop_index("idx_farmacias_adheridas_activo", table_name="farmacias_adheridas")
    op.drop_table("farmacias_adheridas")

    op.drop_index("idx_vademecum_medicamentos_orden", table_name="vademecum_medicamentos")
    op.drop_index("idx_vademecum_medicamentos_activo", table_name="vademecum_medicamentos")
    op.drop_table("vademecum_medicamentos")
