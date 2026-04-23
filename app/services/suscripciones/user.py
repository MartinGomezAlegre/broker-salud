import logging
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.suscripcion import SuscripcionCrear
from app.services.commercial_referrals import (
    build_referral_insert,
    build_referral_update,
    resolve_referral_tracking,
)
from app.services.suscripciones.common import (
    CICLO_DIAS,
    ESTADOS_VIGENTES,
    ciclo_inicial,
    ensure_fecha_vencimiento,
    normalizar_max_beneficiarios,
)

logger = logging.getLogger(__name__)
RENOVACION_ANTICIPADA_DIAS = 7


def contratar_plan(
    db: Session,
    usuario_id: int,
    datos: SuscripcionCrear,
):
    try:
        ensure_fecha_vencimiento(db)

        plan = db.execute(text("""
            SELECT id, nombre, descripcion, tipo, precio_mensual, max_beneficiarios
            FROM planes
            WHERE id = :id AND activo = true
        """), {"id": datos.plan_id}).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado o inactivo")
        referral_tracking = resolve_referral_tracking(db, datos.referral_code)

        vigente = db.execute(text("""
            SELECT s.id, s.plan_id, s.estado, s.fecha_vencimiento, p.max_beneficiarios, p.tipo
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
        """), {
            "usuario_id": usuario_id,
            "estados": list(ESTADOS_VIGENTES),
        }).fetchone()

        max_actual = normalizar_max_beneficiarios(
            vigente.tipo if vigente else None,
            vigente.max_beneficiarios if vigente else None,
        ) or 0
        max_nuevo = normalizar_max_beneficiarios(plan.tipo, plan.max_beneficiarios) or 0

        if vigente:
            if vigente.plan_id == datos.plan_id:
                if _puede_renovar_mismo_plan(vigente):
                    return _actualizar_suscripcion_existente(
                        db=db,
                        suscripcion_id=vigente.id,
                        plan_id=datos.plan_id,
                        precio_pagado=plan.precio_mensual,
                        referral_tracking=referral_tracking,
                    )
                raise HTTPException(status_code=400, detail="Ya tenes este plan como plan actual")

            if vigente.estado in ("activa", "cancelacion_programada") and max_nuevo > max_actual:
                return _actualizar_suscripcion_existente(
                    db=db,
                    suscripcion_id=vigente.id,
                    plan_id=datos.plan_id,
                    precio_pagado=plan.precio_mensual,
                    referral_tracking=referral_tracking,
                )

            raise HTTPException(status_code=400, detail="Ya tenes una suscripcion activa o pendiente de pago")

        historica = db.execute(text("""
            SELECT id
            FROM suscripciones
            WHERE usuario_id = :usuario_id
            ORDER BY COALESCE(fecha_vencimiento, created_at) DESC, created_at DESC
            LIMIT 1
        """), {"usuario_id": usuario_id}).fetchone()

        if historica:
            return _actualizar_suscripcion_existente(
                db=db,
                suscripcion_id=historica.id,
                plan_id=datos.plan_id,
                precio_pagado=plan.precio_mensual,
                referral_tracking=referral_tracking,
            )

        fecha_inicio, fecha_vencimiento = ciclo_inicial()
        referral_columns, referral_values, referral_params = build_referral_insert(referral_tracking)
        resultado = db.execute(text(f"""
            INSERT INTO suscripciones
                (usuario_id, plan_id, estado, fecha_inicio, fecha_vencimiento, precio_pagado{referral_columns})
            VALUES
                (:usuario_id, :plan_id, 'pendiente_pago', :fecha_inicio, :fecha_vencimiento, :precio_pagado{referral_values})
            RETURNING id, plan_id, estado, fecha_inicio, precio_pagado
        """), {
            "usuario_id": usuario_id,
            "plan_id": datos.plan_id,
            "fecha_inicio": fecha_inicio,
            "fecha_vencimiento": fecha_vencimiento,
            "precio_pagado": plan.precio_mensual,
            **referral_params,
        }).fetchone()
        db.commit()

        return resultado
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en contratar_plan: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def mi_suscripcion(
    db: Session,
    usuario_id: int,
):
    try:
        ensure_fecha_vencimiento(db)
        suscripcion = db.execute(text("""
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
        """), {"usuario_id": usuario_id}).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenes suscripciones activas")

        exportado = db.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM auditoria a
                JOIN LATERAL jsonb_array_elements_text(
                    COALESCE(a.datos_nuevos::jsonb -> 'suscripcion_ids', '[]'::jsonb)
                ) AS ids(sid) ON true
                WHERE a.accion = 'exportado_a_mediquo'
                  AND ids.sid = :sid
            ) AS exportado
        """), {"sid": str(suscripcion.id)}).fetchone()

        max_beneficiarios = normalizar_max_beneficiarios(
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


def cancelar_mi_suscripcion(
    db: Session,
    usuario_id: int,
):
    try:
        ensure_fecha_vencimiento(db)
        suscripcion = db.execute(text("""
            SELECT id, estado, fecha_inicio, fecha_vencimiento
            FROM suscripciones
            WHERE usuario_id = :usuario_id
              AND estado NOT IN ('cancelada', 'vencida')
            ORDER BY COALESCE(fecha_vencimiento, created_at) DESC, created_at DESC
            LIMIT 1
        """), {"usuario_id": usuario_id}).fetchone()
        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenes una suscripcion activa para dar de baja")

        if suscripcion.estado == "cancelacion_programada":
            raise HTTPException(status_code=400, detail="La baja ya fue programada para el cierre del ciclo actual")

        nuevo_estado = "cancelada" if suscripcion.estado == "pendiente_pago" else "cancelacion_programada"
        fecha_vencimiento = suscripcion.fecha_vencimiento

        if nuevo_estado == "cancelacion_programada" and fecha_vencimiento is None:
            fecha_base = suscripcion.fecha_inicio or ciclo_inicial()[0]
            fecha_vencimiento = fecha_base + timedelta(days=CICLO_DIAS)
            db.execute(
                text("UPDATE suscripciones SET fecha_vencimiento = :fecha_vencimiento WHERE id = :id"),
                {"fecha_vencimiento": fecha_vencimiento, "id": suscripcion.id},
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


def _actualizar_suscripcion_existente(
    db: Session,
    suscripcion_id: int,
    plan_id: int,
    precio_pagado,
    referral_tracking: dict,
):
    fecha_inicio, fecha_vencimiento = ciclo_inicial()
    referral_set, referral_params = build_referral_update(referral_tracking)
    resultado = db.execute(text(f"""
        UPDATE suscripciones
        SET plan_id = :plan_id,
            estado = 'pendiente_pago',
            fecha_inicio = :fecha_inicio,
            fecha_vencimiento = :fecha_vencimiento,
            precio_pagado = :precio_pagado
            {referral_set}
        WHERE id = :suscripcion_id
        RETURNING id, plan_id, estado, fecha_inicio, precio_pagado
    """), {
        "suscripcion_id": suscripcion_id,
        "plan_id": plan_id,
        "fecha_inicio": fecha_inicio,
        "fecha_vencimiento": fecha_vencimiento,
        "precio_pagado": precio_pagado,
        **referral_params,
    }).fetchone()
    db.commit()
    return resultado


def _puede_renovar_mismo_plan(vigente) -> bool:
    if vigente.estado == "cancelacion_programada":
        return True

    if not vigente.fecha_vencimiento:
        return False

    fecha_vencimiento = vigente.fecha_vencimiento
    if hasattr(fecha_vencimiento, "date"):
        fecha_vencimiento = fecha_vencimiento.date()

    hoy = datetime.utcnow().date()
    dias_restantes = (fecha_vencimiento - hoy).days
    return dias_restantes <= RENOVACION_ANTICIPADA_DIAS
