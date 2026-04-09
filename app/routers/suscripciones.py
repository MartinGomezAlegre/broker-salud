import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.schemas.suscripcion import SuscripcionCrear, SuscripcionRespuesta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/suscripciones", tags=["suscripciones"])

ESTADOS_VIGENTES = ("activa", "pendiente_pago", "cancelacion_programada")


def _normalizar_max_beneficiarios(tipo_plan: str | None, max_beneficiarios: int | None) -> int | None:
    if max_beneficiarios is None:
        return None

    tipo = (tipo_plan or "").lower()
    if tipo == "familiar":
        return min(max_beneficiarios, 4)

    return max_beneficiarios


def _ensure_fecha_vencimiento(db: Session) -> None:
    db.execute(text("ALTER TABLE suscripciones ADD COLUMN IF NOT EXISTS fecha_vencimiento DATE"))
    db.execute(
        text(
            """
            UPDATE suscripciones
            SET fecha_vencimiento = fecha_inicio + INTERVAL '30 days'
            WHERE fecha_vencimiento IS NULL
              AND fecha_inicio IS NOT NULL
            """
        )
    )
    db.commit()


@router.post("", response_model=SuscripcionRespuesta)
def contratar_plan(
    datos: SuscripcionCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        _ensure_fecha_vencimiento(db)
        plan = db.execute(
            text(
                """
                SELECT id, nombre, descripcion, tipo, precio_mensual, max_beneficiarios
                FROM planes
                WHERE id = :id AND activo = true
                """
            ),
            {"id": datos.plan_id},
        ).fetchone()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado o inactivo")

        vigente = db.execute(
            text(
                """
                SELECT s.id, s.plan_id, s.estado,
                       p.max_beneficiarios, p.tipo
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                WHERE s.usuario_id = :usuario_id
                  AND s.estado = ANY(:estados)
                ORDER BY
                    CASE s.estado
                        WHEN 'activa' THEN 1
                        WHEN 'cancelacion_programada' THEN 2
                        WHEN 'pendiente_pago' THEN 3
                        ELSE 4
                    END,
                    COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                    s.created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id, "estados": list(ESTADOS_VIGENTES)},
        ).fetchone()

        max_actual = _normalizar_max_beneficiarios(
            vigente.tipo if vigente else None,
            vigente.max_beneficiarios if vigente else None,
        ) or 0
        max_nuevo = _normalizar_max_beneficiarios(plan.tipo, plan.max_beneficiarios) or 0

        if vigente:
            if vigente.plan_id == datos.plan_id:
                raise HTTPException(status_code=400, detail="Ya tenes este plan como plan actual")

            if vigente.estado in ("activa", "cancelacion_programada") and max_nuevo > max_actual:
                fecha_inicio = date.today()
                fecha_vencimiento = fecha_inicio + timedelta(days=30)

                resultado = db.execute(
                    text(
                        """
                        UPDATE suscripciones
                        SET plan_id = :plan_id,
                            estado = 'pendiente_pago',
                            fecha_inicio = :fecha_inicio,
                            fecha_vencimiento = :fecha_vencimiento,
                            precio_pagado = :precio_pagado
                        WHERE id = :suscripcion_id
                        RETURNING id, plan_id, estado, fecha_inicio, precio_pagado
                        """
                    ),
                    {
                        "suscripcion_id": vigente.id,
                        "plan_id": datos.plan_id,
                        "fecha_inicio": fecha_inicio,
                        "fecha_vencimiento": fecha_vencimiento,
                        "precio_pagado": plan.precio_mensual,
                    },
                ).fetchone()

                db.commit()
                return resultado

            raise HTTPException(status_code=400, detail="Ya tenes una suscripcion activa o pendiente de pago")

        historica = db.execute(
            text(
                """
                SELECT id
                FROM suscripciones
                WHERE usuario_id = :usuario_id
                ORDER BY COALESCE(fecha_vencimiento, created_at) DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id},
        ).fetchone()

        fecha_inicio = date.today()
        fecha_vencimiento = fecha_inicio + timedelta(days=30)

        if historica:
            resultado = db.execute(
                text(
                    """
                    UPDATE suscripciones
                    SET plan_id = :plan_id,
                        estado = 'pendiente_pago',
                        fecha_inicio = :fecha_inicio,
                        fecha_vencimiento = :fecha_vencimiento,
                        precio_pagado = :precio_pagado
                    WHERE id = :suscripcion_id
                    RETURNING id, plan_id, estado, fecha_inicio, precio_pagado
                    """
                ),
                {
                    "suscripcion_id": historica.id,
                    "plan_id": datos.plan_id,
                    "fecha_inicio": fecha_inicio,
                    "fecha_vencimiento": fecha_vencimiento,
                    "precio_pagado": plan.precio_mensual,
                },
            ).fetchone()
        else:
            resultado = db.execute(
                text(
                    """
                    INSERT INTO suscripciones
                        (usuario_id, plan_id, estado, fecha_inicio, fecha_vencimiento, precio_pagado)
                    VALUES
                        (:usuario_id, :plan_id, 'pendiente_pago', :fecha_inicio, :fecha_vencimiento, :precio_pagado)
                    RETURNING id, plan_id, estado, fecha_inicio, precio_pagado
                    """
                ),
                {
                    "usuario_id": usuario_id,
                    "plan_id": datos.plan_id,
                    "fecha_inicio": fecha_inicio,
                    "fecha_vencimiento": fecha_vencimiento,
                    "precio_pagado": plan.precio_mensual,
                },
            ).fetchone()

        db.commit()
        return resultado
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en contratar_plan: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/mia")
def mi_suscripcion(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        _ensure_fecha_vencimiento(db)
        suscripcion = db.execute(
            text(
                """
                SELECT s.*, p.nombre AS nombre_plan,
                       p.descripcion AS descripcion_plan,
                       p.max_beneficiarios,
                       p.tipo AS tipo_plan
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                WHERE s.usuario_id = :usuario_id
                  AND s.estado NOT IN ('cancelada', 'vencida')
                ORDER BY
                    CASE s.estado
                        WHEN 'activa' THEN 1
                        WHEN 'cancelacion_programada' THEN 2
                        WHEN 'pendiente_pago' THEN 3
                        ELSE 4
                    END,
                    COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                    s.created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id},
        ).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenes suscripciones activas")

        exportado = db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM auditoria a
                    JOIN LATERAL jsonb_array_elements_text(
                        COALESCE(a.datos_nuevos::jsonb -> 'suscripcion_ids', '[]'::jsonb)
                    ) AS ids(sid) ON true
                    WHERE a.accion = 'exportado_a_mediquo'
                      AND ids.sid = :sid
                ) AS exportado
                """
            ),
            {"sid": str(suscripcion.id)},
        ).fetchone()

        max_beneficiarios = _normalizar_max_beneficiarios(
            suscripcion.tipo_plan,
            suscripcion.max_beneficiarios,
        )

        return {
            "id": suscripcion.id,
            "plan_id": suscripcion.plan_id,
            "estado": suscripcion.estado,
            "fecha_inicio": suscripcion.fecha_inicio.isoformat() if suscripcion.fecha_inicio else None,
            "fecha_vencimiento": suscripcion.fecha_vencimiento.isoformat() if suscripcion.fecha_vencimiento else None,
            "precio_pagado": float(suscripcion.precio_pagado) if suscripcion.precio_pagado is not None else None,
            "nombre_plan": suscripcion.nombre_plan,
            "descripcion_plan": suscripcion.descripcion_plan,
            "max_beneficiarios": max_beneficiarios,
            "tipo_plan": suscripcion.tipo_plan,
            "fue_exportado": bool(exportado.exportado),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en mi_suscripcion: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.put("/mia/cancelar")
def cancelar_mi_suscripcion(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        _ensure_fecha_vencimiento(db)
        suscripcion = db.execute(
            text(
                """
                SELECT id, estado, fecha_inicio, fecha_vencimiento
                FROM suscripciones
                WHERE usuario_id = :usuario_id
                  AND estado NOT IN ('cancelada', 'vencida')
                ORDER BY COALESCE(fecha_vencimiento, created_at) DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id},
        ).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenes una suscripcion activa para dar de baja")

        if suscripcion.estado == "cancelacion_programada":
            raise HTTPException(status_code=400, detail="La baja ya fue programada para el cierre del ciclo actual")

        nuevo_estado = "cancelada" if suscripcion.estado == "pendiente_pago" else "cancelacion_programada"
        fecha_vencimiento = suscripcion.fecha_vencimiento
        if nuevo_estado == "cancelacion_programada" and fecha_vencimiento is None:
            fecha_base = suscripcion.fecha_inicio or date.today()
            fecha_vencimiento = fecha_base + timedelta(days=30)
            db.execute(
                text("UPDATE suscripciones SET fecha_vencimiento = :fv WHERE id = :id"),
                {"fv": fecha_vencimiento, "id": suscripcion.id},
            )

        db.execute(
            text("UPDATE suscripciones SET estado = :estado WHERE id = :id"),
            {"estado": nuevo_estado, "id": suscripcion.id},
        )
        db.commit()

        if nuevo_estado == "cancelada":
            return {"ok": True, "mensaje": "Suscripcion cancelada correctamente"}

        return {
            "ok": True,
            "mensaje": "La baja fue programada. Mantendras el acceso hasta el fin de tu suscripcion actual.",
            "fecha_vencimiento": fecha_vencimiento.isoformat() if fecha_vencimiento else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en cancelar_mi_suscripcion: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
