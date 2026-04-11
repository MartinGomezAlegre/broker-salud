from datetime import date, timedelta
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.facturacion import PagoManual

logger = logging.getLogger(__name__)


def listar_pagos(
    db: Session,
    estado: str | None,
    pasarela: str | None,
    fecha_desde: date | None,
    fecha_hasta: date | None,
):
    try:
        condiciones = ["1=1"]
        params: dict = {}

        if estado:
            condiciones.append("p.estado = :estado")
            params["estado"] = estado
        if pasarela:
            condiciones.append("p.pasarela = :pasarela")
            params["pasarela"] = pasarela
        if fecha_desde:
            condiciones.append("p.created_at >= :fecha_desde")
            params["fecha_desde"] = fecha_desde
        if fecha_hasta:
            condiciones.append("p.created_at < :fecha_hasta")
            params["fecha_hasta"] = fecha_hasta + timedelta(days=1)

        where = " AND ".join(condiciones)

        rows = db.execute(text(f"""
            SELECT p.id,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email,
                   p.monto, p.moneda, p.pasarela, p.estado, p.tipo,
                   p.fecha_aprobacion, p.created_at
            FROM pagos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE {where}
            ORDER BY p.created_at DESC
        """), params).fetchall()

        return [
            {
                "id": row.id,
                "usuario_nombre": row.usuario_nombre,
                "usuario_email": row.usuario_email,
                "monto": float(row.monto) if row.monto is not None else None,
                "moneda": row.moneda,
                "pasarela": row.pasarela,
                "estado": row.estado,
                "tipo": row.tipo,
                "fecha": row.fecha_aprobacion.isoformat() if row.fecha_aprobacion else row.created_at.isoformat(),
                "fecha_aprobacion": row.fecha_aprobacion.isoformat() if row.fecha_aprobacion else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def pago_manual(
    db: Session,
    datos: PagoManual,
):
    try:
        plan = db.execute(
            text("SELECT id, precio_mensual FROM planes WHERE id = :id AND activo = true"),
            {"id": datos.plan_id},
        ).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado o inactivo")

        precio_esperado = float(plan.precio_mensual or 0)
        if datos.monto < 0 or (precio_esperado > 0 and datos.monto <= 0):
            raise HTTPException(status_code=400, detail="El monto del pago manual debe ser mayor a cero")
        if precio_esperado > 0 and abs(datos.monto - precio_esperado) > 0.01:
            logger.warning(
                "Pago manual con monto distinto al precio del plan. usuario_id=%s plan_id=%s monto=%s precio_plan=%s",
                datos.usuario_id,
                datos.plan_id,
                datos.monto,
                precio_esperado,
            )

        pago = db.execute(text("""
            INSERT INTO pagos (usuario_id, monto, pasarela, estado, tipo, fecha_aprobacion)
            VALUES (:usuario_id, :monto, 'manual', 'aprobado', :tipo, NOW())
            RETURNING id
        """), {
            "usuario_id": datos.usuario_id,
            "monto": datos.monto,
            "tipo": datos.descripcion or "pago_manual",
        }).fetchone()

        suscripcion_pendiente = db.execute(text("""
            SELECT id FROM suscripciones
            WHERE usuario_id = :uid AND estado = 'pendiente_pago'
            ORDER BY created_at DESC LIMIT 1
        """), {"uid": datos.usuario_id}).fetchone()

        suscripcion_activa = db.execute(text("""
            SELECT id FROM suscripciones
            WHERE usuario_id = :uid AND estado = 'activa'
            ORDER BY created_at DESC LIMIT 1
        """), {"uid": datos.usuario_id}).fetchone()

        fecha_vencimiento = date.today() + timedelta(days=30)
        suscripcion_id = None

        if suscripcion_pendiente:
            db.execute(text("""
                UPDATE suscripciones
                SET plan_id = :plan_id,
                    estado = 'activa',
                    fecha_inicio = CURRENT_DATE,
                    fecha_vencimiento = :fecha_vencimiento,
                    precio_pagado = :precio_pagado
                WHERE id = :id
            """), {
                "id": suscripcion_pendiente.id,
                "plan_id": datos.plan_id,
                "fecha_vencimiento": fecha_vencimiento,
                "precio_pagado": datos.monto,
            })
            suscripcion_id = suscripcion_pendiente.id
        elif suscripcion_activa:
            raise HTTPException(status_code=400, detail="El usuario ya tiene una suscripcion activa")
        else:
            nueva = db.execute(text("""
                INSERT INTO suscripciones
                  (usuario_id, plan_id, estado, fecha_inicio, fecha_vencimiento, precio_pagado)
                VALUES (:usuario_id, :plan_id, 'activa', CURRENT_DATE, :fecha_vencimiento, :precio_pagado)
                RETURNING id
            """), {
                "usuario_id": datos.usuario_id,
                "plan_id": datos.plan_id,
                "fecha_vencimiento": fecha_vencimiento,
                "precio_pagado": datos.monto,
            }).fetchone()
            suscripcion_id = nueva.id

        db.commit()
        return {
            "pago_id": pago.id,
            "suscripcion_id": suscripcion_id,
            "mensaje": "Pago manual registrado y suscripcion activada correctamente",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
