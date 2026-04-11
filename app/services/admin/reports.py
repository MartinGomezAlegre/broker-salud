from datetime import date, datetime
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def metricas_retencion(db: Session):
    try:
        rows = db.execute(text("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', s.created_at), 'YYYY-MM') AS mes,
                COUNT(*) AS nuevos,
                COUNT(*) FILTER (WHERE s.estado = 'activa') AS activos_siguiente_mes
            FROM suscripciones s
            WHERE s.created_at >= DATE_TRUNC('month', NOW()) - INTERVAL '5 months'
            GROUP BY DATE_TRUNC('month', s.created_at)
            ORDER BY DATE_TRUNC('month', s.created_at) ASC
        """)).fetchall()

        resultado = []
        for row in rows:
            tasa = round((row.activos_siguiente_mes / row.nuevos * 100), 2) if row.nuevos > 0 else 0
            resultado.append({
                "mes": row.mes,
                "nuevos": row.nuevos,
                "activos_al_mes_siguiente": row.activos_siguiente_mes,
                "tasa_retencion": tasa,
            })
        return resultado
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def metricas_embudo(db: Session):
    try:
        total_usuarios = db.execute(text(
            "SELECT COUNT(*) as total FROM usuarios"
        )).fetchone().total

        iniciaron_checkout = db.execute(text("""
            SELECT COUNT(DISTINCT usuario_id) as total FROM suscripciones
        """)).fetchone().total

        completaron_pago = db.execute(text("""
            SELECT COUNT(*) as total
            FROM suscripciones
            WHERE estado IN ('activa', 'cancelacion_programada')
        """)).fetchone().total

        tasa_reg_checkout = round(iniciaron_checkout / total_usuarios * 100, 2) if total_usuarios > 0 else 0
        tasa_checkout_pago = round(completaron_pago / iniciaron_checkout * 100, 2) if iniciaron_checkout > 0 else 0

        return {
            "visitantes_registrados": total_usuarios,
            "iniciaron_checkout": iniciaron_checkout,
            "completaron_pago": completaron_pago,
            "tasa_registro_a_checkout": tasa_reg_checkout,
            "tasa_checkout_a_pago": tasa_checkout_pago,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def reporte_mensual(db: Session, mes: str | None):
    try:
        if mes:
            try:
                inicio_mes = datetime.strptime(mes, "%Y-%m").date().replace(day=1)
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de mes inválido. Usar: YYYY-MM")
        else:
            hoy = date.today()
            inicio_mes = hoy.replace(day=1)

        if inicio_mes.month == 1:
            inicio_mes_ant = inicio_mes.replace(year=inicio_mes.year - 1, month=12)
        else:
            inicio_mes_ant = inicio_mes.replace(month=inicio_mes.month - 1)

        if inicio_mes.month == 12:
            fin_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1)
        else:
            fin_mes = inicio_mes.replace(month=inicio_mes.month + 1)

        def _mrr(desde, hasta):
            return float(db.execute(text("""
                SELECT COALESCE(SUM(precio_pagado), 0) as mrr FROM suscripciones
                WHERE estado IN ('activa', 'cancelacion_programada')
                AND created_at >= :desde AND created_at < :hasta
            """), {"desde": desde, "hasta": hasta}).fetchone().mrr)

        def _count(tabla_campo, desde, hasta, extra=""):
            return db.execute(text(f"""
                SELECT COUNT(*) as total FROM {tabla_campo}
                WHERE created_at >= :desde AND created_at < :hasta {extra}
            """), {"desde": desde, "hasta": hasta}).fetchone().total

        mrr_mes = _mrr(inicio_mes, fin_mes)
        mrr_ant = _mrr(inicio_mes_ant, inicio_mes)
        var_mrr = round((mrr_mes - mrr_ant) / mrr_ant * 100, 2) if mrr_ant > 0 else 0

        nuevas = _count("suscripciones", inicio_mes, fin_mes)
        nuevas_ant = _count("suscripciones", inicio_mes_ant, inicio_mes)
        var_nuevas = round((nuevas - nuevas_ant) / nuevas_ant * 100, 2) if nuevas_ant > 0 else 0

        canceladas = _count("suscripciones", inicio_mes, fin_mes, "AND estado = 'cancelada'")
        canceladas_ant = _count("suscripciones", inicio_mes_ant, inicio_mes, "AND estado = 'cancelada'")
        var_cancel = round((canceladas - canceladas_ant) / canceladas_ant * 100, 2) if canceladas_ant > 0 else 0

        nuevos_usuarios = _count("usuarios", inicio_mes, fin_mes)

        empresas_nuevas = db.execute(text("""
            SELECT COUNT(*) as total FROM empresas
            WHERE created_at >= :desde AND created_at < :hasta
        """), {"desde": inicio_mes, "hasta": fin_mes}).fetchone().total

        revenue_plan = db.execute(text("""
            SELECT p.nombre, COALESCE(SUM(s.precio_pagado), 0) as revenue,
                   COUNT(s.id) as suscriptores
            FROM planes p
            LEFT JOIN suscripciones s ON s.plan_id = p.id
                AND s.created_at >= :desde AND s.created_at < :hasta
            GROUP BY p.nombre
            ORDER BY revenue DESC
        """), {"desde": inicio_mes, "hasta": fin_mes}).fetchall()

        top_plan = revenue_plan[0].nombre if revenue_plan and revenue_plan[0].revenue > 0 else None

        return {
            "mes": inicio_mes.strftime("%Y-%m"),
            "mrr": mrr_mes,
            "mrr_mes_anterior": mrr_ant,
            "variacion_mrr": var_mrr,
            "nuevas_suscripciones": nuevas,
            "nuevas_mes_anterior": nuevas_ant,
            "variacion_nuevas": var_nuevas,
            "cancelaciones": canceladas,
            "cancelaciones_mes_anterior": canceladas_ant,
            "variacion_cancelaciones": var_cancel,
            "nuevos_usuarios": nuevos_usuarios,
            "empresas_nuevas": empresas_nuevas,
            "revenue_por_plan": [
                {"plan": row.nombre, "revenue": float(row.revenue), "suscriptores": row.suscriptores}
                for row in revenue_plan
            ],
            "top_plan": top_plan,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
