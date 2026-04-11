from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.upsells import UpsellSeguroActualizar
from app.services.upsells.common import ensure_upsells_table, logger, serialize_upsell, validate_estado


def listar_upsells_seguro(
    db: Session,
    estado: str | None,
):
    try:
        ensure_upsells_table(db)
        if estado:
            validate_estado(estado)

        filtro = "WHERE us.estado = :estado" if estado else ""
        params = {"estado": estado} if estado else {}
        rows = db.execute(text(f"""
            SELECT us.id, us.usuario_id, us.suscripcion_id, us.plan_nombre, us.precio_ofertado,
                   us.estado, us.nota_admin, us.created_at, us.updated_at,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email
            FROM upsells_seguro us
            JOIN usuarios u ON u.id = us.usuario_id
            {filtro}
            ORDER BY us.updated_at DESC NULLS LAST, us.created_at DESC
        """), params).fetchall()

        return [
            {
                **serialize_upsell(row),
                "usuario_nombre": row.usuario_nombre,
                "usuario_email": row.usuario_email,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_upsells_seguro: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_upsell_seguro(
    db: Session,
    upsell_id: int,
    datos: UpsellSeguroActualizar,
):
    try:
        ensure_upsells_table(db)
        validate_estado(datos.estado)

        row = db.execute(
            text("SELECT id FROM upsells_seguro WHERE id = :id"),
            {"id": upsell_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Upsell no encontrado")

        actualizado = db.execute(text("""
            UPDATE upsells_seguro
            SET estado = :estado,
                nota_admin = :nota_admin,
                updated_at = NOW()
            WHERE id = :id
            RETURNING id, estado, nota_admin, updated_at
        """), {
            "id": upsell_id,
            "estado": datos.estado,
            "nota_admin": datos.nota_admin,
        }).fetchone()
        db.commit()

        return {
            "id": actualizado.id,
            "estado": actualizado.estado,
            "nota_admin": actualizado.nota_admin,
            "updated_at": actualizado.updated_at.isoformat() if actualizado.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en actualizar_upsell_seguro: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
