import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.auth import get_current_user
from app.schemas.suscripcion import SuscripcionCrear, SuscripcionRespuesta
from datetime import date, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/suscripciones",
    tags=["suscripciones"]
)

@router.post("", response_model=SuscripcionRespuesta)
def contratar_plan(
    datos: SuscripcionCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        plan = db.execute(
            text("SELECT * FROM planes WHERE id = :id AND activo = true"),
            {"id": datos.plan_id}
        ).fetchone()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado o inactivo")

        suscripcion_existente = db.execute(
            text("""SELECT id FROM suscripciones
                    WHERE usuario_id = :usuario_id
                    AND estado IN ('activa', 'pendiente_pago')"""),
            {"usuario_id": usuario_id}
        ).fetchone()

        if suscripcion_existente:
            raise HTTPException(status_code=400, detail="Ya tenés una suscripción activa o pendiente de pago")

        fecha_inicio = date.today()
        fecha_vencimiento = fecha_inicio + timedelta(days=30)

        resultado = db.execute(
            text("""INSERT INTO suscripciones
                    (usuario_id, plan_id, estado, fecha_inicio, fecha_vencimiento, precio_pagado)
                    VALUES (:usuario_id, :plan_id, 'pendiente_pago', :fecha_inicio, :fecha_vencimiento, :precio_pagado)
                    RETURNING *"""),
            {
                "usuario_id": usuario_id,
                "plan_id": datos.plan_id,
                "fecha_inicio": fecha_inicio,
                "fecha_vencimiento": fecha_vencimiento,
                "precio_pagado": plan.precio_mensual
            }
        ).fetchone()

        db.commit()
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en contratar_plan: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/mia")
def mi_suscripcion(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        suscripcion = db.execute(
            text("""SELECT s.*, p.nombre AS nombre_plan,
                           p.descripcion AS descripcion_plan
                    FROM suscripciones s
                    JOIN planes p ON p.id = s.plan_id
                    WHERE s.usuario_id = :usuario_id
                      AND s.estado != 'cancelada'
                    ORDER BY s.created_at DESC LIMIT 1"""),
            {"usuario_id": usuario_id}
        ).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenés suscripciones activas")

        exportado = db.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM auditoria a
                    JOIN LATERAL jsonb_array_elements_text(
                        COALESCE(a.datos_nuevos::jsonb -> 'suscripcion_ids', '[]'::jsonb)
                    ) AS ids(sid) ON true
                    WHERE a.accion = 'exportado_a_mediquo'
                      AND ids.sid = :sid
                ) AS exportado
            """),
            {"sid": str(suscripcion.id)}
        ).fetchone()

        return {
            "id": suscripcion.id,
            "plan_id": suscripcion.plan_id,
            "estado": suscripcion.estado,
            "fecha_inicio": suscripcion.fecha_inicio.isoformat() if suscripcion.fecha_inicio else None,
            "fecha_vencimiento": suscripcion.fecha_vencimiento.isoformat() if suscripcion.fecha_vencimiento else None,
            "precio_pagado": float(suscripcion.precio_pagado) if suscripcion.precio_pagado is not None else None,
            "nombre_plan": suscripcion.nombre_plan,
            "descripcion_plan": suscripcion.descripcion_plan,
            "fue_exportado": bool(exportado.exportado),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en mi_suscripcion: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
