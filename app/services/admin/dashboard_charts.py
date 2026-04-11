from datetime import date, timedelta
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def metricas_grafico(db: Session):
    try:
        rows = db.execute(text("""
            SELECT DATE(created_at) as fecha, COUNT(*) as nuevas
            FROM suscripciones
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY fecha ASC
        """)).fetchall()

        por_dia = {row.fecha: row.nuevas for row in rows}
        total_previo = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE created_at < NOW() - INTERVAL '30 days'
        """)).fetchone().total

        resultado = []
        acumulado = total_previo
        hoy = date.today()
        inicio = hoy - timedelta(days=29)

        for i in range(30):
            dia = inicio + timedelta(days=i)
            nuevas = por_dia.get(dia, 0)
            acumulado += nuevas
            resultado.append({
                "fecha": dia.isoformat(),
                "nuevas": nuevas,
                "total_acumulado": acumulado,
            })

        return resultado
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        return []
