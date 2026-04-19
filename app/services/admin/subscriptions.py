import logging

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.admin import ActualizarPlan, CambiarEstadoSuscripcion
from app.services.email import dispatch_email, enviar_email_suscripcion_activa

logger = logging.getLogger(__name__)

ESTADOS_PERMITIDOS = {"activa", "cancelada", "cancelacion_programada", "pendiente_pago", "vencida"}


def listar_suscripciones(
    db: Session,
    estado: str | None,
    limit: int,
    offset: int,
):
    try:
        filtro = "AND s.estado = :estado" if estado else ""
        params: dict = {"limit": limit, "offset": offset}
        if estado:
            params["estado"] = estado

        rows = db.execute(text(f"""
            SELECT s.id,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email,
                   p.nombre AS plan_nombre,
                   s.estado,
                   s.precio_pagado,
                   s.fecha_inicio,
                   s.created_at
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE 1=1 {filtro}
            ORDER BY s.created_at DESC LIMIT :limit OFFSET :offset
        """), params).fetchall()

        return [
            {
                "id": row.id,
                "nombre_completo": row.usuario_nombre,
                "email": row.usuario_email,
                "plan_nombre": row.plan_nombre,
                "estado": row.estado,
                "precio_pagado": float(row.precio_pagado) if row.precio_pagado is not None else None,
                "fecha_inicio": row.fecha_inicio.isoformat() if row.fecha_inicio else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_plan(
    db: Session,
    plan_id: int,
    datos: ActualizarPlan,
):
    try:
        plan = db.execute(
            text("SELECT * FROM planes WHERE id = :id"),
            {"id": plan_id},
        ).fetchone()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        campos = []
        params = {"id": plan_id}

        if datos.activo is not None:
            campos.append("activo = :activo")
            params["activo"] = datos.activo

        if datos.precio_mensual is not None:
            campos.append("precio_mensual = :precio_mensual")
            params["precio_mensual"] = datos.precio_mensual

        if campos:
            db.execute(
                text(f"UPDATE planes SET {', '.join(campos)} WHERE id = :id"),
                params,
            )
            db.commit()

        plan_actualizado = db.execute(
            text("SELECT * FROM planes WHERE id = :id"),
            {"id": plan_id},
        ).fetchone()

        return {
            "id": plan_actualizado.id,
            "nombre": plan_actualizado.nombre,
            "precio_mensual": float(plan_actualizado.precio_mensual),
            "activo": plan_actualizado.activo,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def cambiar_estado_suscripcion(
    db: Session,
    suscripcion_id: int,
    datos: CambiarEstadoSuscripcion,
    background_tasks: BackgroundTasks | None = None,
):
    try:
        if datos.estado not in ESTADOS_PERMITIDOS:
            raise HTTPException(
                status_code=400,
                detail=f"Estado invalido. Permitidos: {', '.join(ESTADOS_PERMITIDOS)}",
            )

        row = db.execute(text("""
            SELECT s.id, s.estado, s.precio_pagado, s.fecha_inicio,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email,
                   p.nombre AS plan_nombre
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE s.id = :id
        """), {"id": suscripcion_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Suscripcion no encontrada")

        estado_anterior = row.estado

        db.execute(
            text("UPDATE suscripciones SET estado = :estado WHERE id = :id"),
            {"estado": datos.estado, "id": suscripcion_id},
        )

        if datos.estado == "activa" and estado_anterior != "activa":
            venc = db.execute(
                text("SELECT fecha_vencimiento FROM suscripciones WHERE id = :id"),
                {"id": suscripcion_id},
            ).fetchone()
            fecha_venc_str = venc.fecha_vencimiento.isoformat() if venc and venc.fecha_vencimiento else "-"
            precio = float(row.precio_pagado) if row.precio_pagado is not None else 0.0

            dispatch_email(
                background_tasks,
                enviar_email_suscripcion_activa,
                row.usuario_email,
                row.usuario_nombre.split()[0],
                row.plan_nombre,
                fecha_venc_str,
                precio,
            )

        db.execute(text("""
            INSERT INTO historial_suscripciones
              (suscripcion_id, campo_modificado, valor_anterior, valor_nuevo, motivo)
            VALUES (:suscripcion_id, 'estado', :valor_anterior, :valor_nuevo, :motivo)
        """), {
            "suscripcion_id": suscripcion_id,
            "valor_anterior": estado_anterior,
            "valor_nuevo": datos.estado,
            "motivo": datos.motivo,
        })

        db.commit()

        return {
            "id": row.id,
            "usuario_nombre": row.usuario_nombre,
            "usuario_email": row.usuario_email,
            "plan_nombre": row.plan_nombre,
            "estado": datos.estado,
            "precio_pagado": float(row.precio_pagado) if row.precio_pagado is not None else None,
            "fecha_inicio": row.fecha_inicio.isoformat() if row.fecha_inicio else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
