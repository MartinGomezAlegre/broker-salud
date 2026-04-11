from datetime import date
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def procesar_vencimientos(db: Session):
    try:
        vencidas = db.execute(text("""
            SELECT s.id, u.email, u.nombre, p.nombre AS plan_nombre
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE s.estado IN ('activa', 'cancelacion_programada')
              AND s.fecha_vencimiento < CURRENT_DATE
        """)).fetchall()

        if not vencidas:
            return {"procesadas": 0}

        ids = [row.id for row in vencidas]
        db.execute(text("""
            UPDATE suscripciones
            SET estado = CASE
                WHEN estado = 'cancelacion_programada' THEN 'cancelada'
                ELSE 'vencida'
            END
            WHERE id = ANY(:ids)
        """), {"ids": ids})
        db.commit()

        from app.services.email import enviar_email_plan_vencido

        for row in vencidas:
            try:
                enviar_email_plan_vencido(row.email, row.nombre, row.plan_nombre)
            except Exception as exc:
                logger.error("Error enviando email vencido a %s: %s", row.email, exc)

        return {"procesadas": len(vencidas)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en procesar_vencimientos: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def enviar_recordatorios(db: Session):
    try:
        proximas = db.execute(text("""
            SELECT s.id, s.fecha_vencimiento,
                   u.email, u.nombre,
                   p.nombre AS plan_nombre
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE s.estado = 'activa'
              AND s.fecha_vencimiento BETWEEN CURRENT_DATE + 1
                                          AND CURRENT_DATE + 7
        """)).fetchall()

        from app.services.email import enviar_email_vencimiento_proximo

        enviados = 0
        for row in proximas:
            try:
                dias = (row.fecha_vencimiento - date.today()).days
                enviar_email_vencimiento_proximo(
                    row.email,
                    row.nombre,
                    row.plan_nombre,
                    dias,
                    row.fecha_vencimiento.isoformat(),
                )
                enviados += 1
            except Exception as exc:
                logger.error("Error enviando recordatorio a %s: %s", row.email, exc)

        return {"enviados": enviados}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en enviar_recordatorios: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
