from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.upsells import UpsellSeguroCrear
from app.services.upsells.common import ensure_upsells_table, logger, precio_seguro, serialize_upsell


def mi_upsell_seguro(
    db: Session,
    usuario_id: int,
):
    try:
        ensure_upsells_table(db)
        row = db.execute(text("""
            SELECT id, usuario_id, suscripcion_id, plan_nombre, precio_ofertado,
                   estado, nota_admin, created_at, updated_at
            FROM upsells_seguro
            WHERE usuario_id = :usuario_id
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
        """), {"usuario_id": usuario_id}).fetchone()

        if not row:
            return None

        return serialize_upsell(row)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en mi_upsell_seguro: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def crear_upsell_seguro(
    db: Session,
    usuario_id: int,
    datos: UpsellSeguroCrear,
):
    try:
        ensure_upsells_table(db)
        suscripcion = db.execute(text("""
            SELECT s.id, p.nombre AS plan_nombre, p.max_beneficiarios, p.tipo
            FROM suscripciones s
            JOIN planes p ON p.id = s.plan_id
            WHERE s.usuario_id = :usuario_id
              AND s.estado IN ('activa', 'cancelacion_programada', 'pendiente_pago')
            ORDER BY COALESCE(s.fecha_vencimiento, s.created_at) DESC, s.created_at DESC
            LIMIT 1
        """), {"usuario_id": usuario_id}).fetchone()
        if not suscripcion:
            raise HTTPException(status_code=400, detail="Necesitas una suscripcion iniciada para solicitar el seguro medico")

        precio = precio_seguro(suscripcion.max_beneficiarios, suscripcion.tipo)
        existente = db.execute(text("""
            SELECT id
            FROM upsells_seguro
            WHERE usuario_id = :usuario_id
              AND suscripcion_id = :suscripcion_id
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
        """), {
            "usuario_id": usuario_id,
            "suscripcion_id": suscripcion.id,
        }).fetchone()

        if existente:
            row = db.execute(text("""
                UPDATE upsells_seguro
                SET precio_ofertado = :precio_ofertado,
                    estado = :estado,
                    updated_at = NOW()
                WHERE id = :id
                RETURNING id, usuario_id, suscripcion_id, plan_nombre, precio_ofertado,
                          estado, nota_admin, created_at, updated_at
            """), {
                "id": existente.id,
                "precio_ofertado": precio,
                "estado": "nuevo" if datos.acepta else "rechazado",
            }).fetchone()
        else:
            row = db.execute(text("""
                INSERT INTO upsells_seguro
                    (usuario_id, suscripcion_id, plan_nombre, precio_ofertado, estado)
                VALUES
                    (:usuario_id, :suscripcion_id, :plan_nombre, :precio_ofertado, :estado)
                RETURNING id, usuario_id, suscripcion_id, plan_nombre, precio_ofertado,
                          estado, nota_admin, created_at, updated_at
            """), {
                "usuario_id": usuario_id,
                "suscripcion_id": suscripcion.id,
                "plan_nombre": suscripcion.plan_nombre,
                "precio_ofertado": precio,
                "estado": "nuevo" if datos.acepta else "rechazado",
            }).fetchone()

        db.commit()
        return serialize_upsell(row)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_upsell_seguro: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
