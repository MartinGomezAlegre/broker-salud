import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def metricas_empresas(db: Session):
    try:
        totales = db.execute(text("""
            SELECT
                COUNT(*) AS total_empresas,
                COUNT(*) FILTER (WHERE activo = true) AS empresas_activas
            FROM empresas
        """)).fetchone()

        empleados_activos = db.execute(text("""
            SELECT COUNT(*) AS total FROM empleados_empresa WHERE activo = true
        """)).fetchone().total

        mrr = db.execute(text("""
            SELECT COALESCE(SUM(precio_total), 0) AS mrr
            FROM suscripciones_empresariales WHERE estado = 'activa'
        """)).fetchone().mrr

        vencen_semana = db.execute(text("""
            SELECT COUNT(*) AS total FROM suscripciones_empresariales
            WHERE estado NOT IN ('cancelada', 'vencida')
            AND proximo_cobro BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
        """)).fetchone().total

        pendiente_pago = db.execute(text("""
            SELECT COUNT(*) AS total FROM suscripciones_empresariales
            WHERE estado = 'pendiente_pago'
        """)).fetchone().total

        return {
            "total_empresas": totales.total_empresas,
            "empresas_activas": totales.empresas_activas,
            "total_empleados_activos": empleados_activos,
            "mrr_empresarial": float(mrr),
            "empresas_vencen_esta_semana": vencen_semana,
            "empresas_pendiente_pago": pendiente_pago,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
