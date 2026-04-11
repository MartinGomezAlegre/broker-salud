import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def resumen_facturacion(db: Session):
    try:
        mes_actual = db.execute(text("""
            SELECT
                COALESCE(SUM(monto) FILTER (WHERE estado = 'aprobado'), 0) AS total,
                COUNT(*) FILTER (WHERE estado = 'aprobado') AS aprobados,
                COUNT(*) FILTER (WHERE estado = 'rechazado') AS rechazados
            FROM pagos
            WHERE created_at >= DATE_TRUNC('month', NOW())
        """)).fetchone()

        mes_anterior = db.execute(text("""
            SELECT COALESCE(SUM(monto), 0) AS total FROM pagos
            WHERE estado = 'aprobado'
              AND created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
              AND created_at < DATE_TRUNC('month', NOW())
        """)).fetchone()

        total_actual = float(mes_actual.total)
        total_anterior = float(mes_anterior.total)
        variacion = round((total_actual - total_anterior) / total_anterior * 100, 2) if total_anterior > 0 else 0

        por_pasarela = db.execute(text("""
            SELECT pasarela,
                   COALESCE(SUM(monto), 0) AS total,
                   COUNT(*) AS cantidad
            FROM pagos
            WHERE estado = 'aprobado'
              AND created_at >= DATE_TRUNC('month', NOW())
            GROUP BY pasarela
            ORDER BY total DESC
        """)).fetchall()

        return {
            "total_mes": total_actual,
            "total_mes_anterior": total_anterior,
            "variacion_porcentual": variacion,
            "pagos_aprobados": mes_actual.aprobados,
            "pagos_rechazados": mes_actual.rechazados,
            "por_pasarela": [
                {
                    "pasarela": row.pasarela,
                    "total": float(row.total),
                    "cantidad": row.cantidad,
                }
                for row in por_pasarela
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def listar_facturas(
    db: Session,
    tipo: str | None,
    mes: str | None,
):
    try:
        condiciones = ["1=1"]
        params: dict = {}

        if tipo:
            condiciones.append("f.tipo = :tipo")
            params["tipo"] = tipo
        if mes:
            condiciones.append("TO_CHAR(f.fecha_emision, 'YYYY-MM') = :mes")
            params["mes"] = mes

        where = " AND ".join(condiciones)

        rows = db.execute(text(f"""
            SELECT id, numero_factura, tipo, razon_social,
                   monto_total, estado, fecha_emision
            FROM facturas f
            WHERE {where}
            ORDER BY fecha_emision DESC
        """), params).fetchall()

        return [
            {
                "id": row.id,
                "numero_factura": row.numero_factura,
                "tipo": row.tipo,
                "razon_social": row.razon_social,
                "monto_total": float(row.monto_total) if row.monto_total is not None else None,
                "estado": row.estado,
                "fecha_emision": row.fecha_emision.isoformat() if row.fecha_emision else None,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
