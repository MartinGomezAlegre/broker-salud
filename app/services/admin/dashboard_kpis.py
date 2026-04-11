import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def dashboard(db: Session):
    try:
        mrr = db.execute(text("""
            SELECT COALESCE(SUM(precio_pagado), 0) as mrr
            FROM suscripciones
            WHERE estado IN ('activa', 'cancelacion_programada')
        """)).fetchone()
        activos = db.execute(text("""
            SELECT COUNT(*) as total
            FROM suscripciones
            WHERE estado IN ('activa', 'cancelacion_programada')
        """)).fetchone()
        nuevos_hoy = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE DATE(created_at) = CURRENT_DATE
        """)).fetchone()
        nuevas_semana = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """)).fetchone()
        cancelaciones = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE estado = 'cancelada'
              AND created_at >= DATE_TRUNC('month', NOW())
        """)).fetchone()
        total_usuarios = db.execute(text("SELECT COUNT(*) as total FROM usuarios")).fetchone()
        sin_suscripcion = db.execute(text("""
            SELECT COUNT(*) as total FROM usuarios
            WHERE NOT EXISTS (
                SELECT 1
                FROM suscripciones s
                WHERE s.usuario_id = usuarios.id
                  AND s.estado IN ('activa', 'cancelacion_programada')
            )
        """)).fetchone()
        total_mes_anterior = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
              AND created_at < DATE_TRUNC('month', NOW())
        """)).fetchone()
        pendientes_pago = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones WHERE estado = 'pendiente_pago'
        """)).fetchone()
        nuevos_registros_hoy = db.execute(text("""
            SELECT COUNT(*) as total FROM usuarios
            WHERE DATE(created_at) = CURRENT_DATE
        """)).fetchone()
        mrr_empresarial = db.execute(text("""
            SELECT COALESCE(SUM(precio_total), 0) as mrr
            FROM suscripciones_empresariales WHERE estado = 'activa'
        """)).fetchone()
        empresas_activas = db.execute(text("""
            SELECT COUNT(*) as total FROM empresas WHERE activo = true
        """)).fetchone()
        empleados_activos = db.execute(text("""
            SELECT COUNT(*) as total FROM empleados_empresa WHERE activo = true
        """)).fetchone()

        churn_rate = 0
        if total_mes_anterior.total > 0:
            churn_rate = round((cancelaciones.total / total_mes_anterior.total) * 100, 2)

        planes = db.execute(text("""
            SELECT p.nombre, COUNT(s.id) as suscriptores
            FROM planes p
            LEFT JOIN suscripciones s
              ON p.id = s.plan_id
             AND s.estado IN ('activa', 'cancelacion_programada')
            GROUP BY p.nombre
            ORDER BY suscriptores DESC
        """)).fetchall()
        revenue_por_plan = db.execute(text("""
            SELECT p.nombre, COUNT(s.id) as suscriptores,
                   COALESCE(SUM(s.precio_pagado), 0) as revenue
            FROM planes p
            LEFT JOIN suscripciones s ON p.id = s.plan_id
              AND s.estado IN ('activa', 'cancelacion_programada', 'pendiente_pago')
            GROUP BY p.nombre
        """)).fetchall()
        ultimas_suscripciones = db.execute(text("""
            SELECT s.id,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email,
                   p.nombre AS plan_nombre,
                   s.estado, s.created_at
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            ORDER BY s.created_at DESC LIMIT 5
        """)).fetchall()
        ultimas_actividades = db.execute(text("""
            SELECT accion, tabla_afectada, created_at
            FROM auditoria ORDER BY created_at DESC LIMIT 10
        """)).fetchall()

        mrr_val = float(mrr.mrr)
        return {
            "mrr": mrr_val,
            "mrr_personal": mrr_val,
            "mrr_empresarial": float(mrr_empresarial.mrr),
            "arr": round(mrr_val * 12, 2),
            "suscriptores_activos": activos.total,
            "nuevos_hoy": nuevos_hoy.total,
            "nuevas_suscripciones_semana": nuevas_semana.total,
            "cancelaciones_mes": cancelaciones.total,
            "churn_rate": churn_rate,
            "churn_rate_porcentaje": churn_rate,
            "total_usuarios": total_usuarios.total,
            "usuarios_sin_convertir": sin_suscripcion.total,
            "tasa_conversion": round((activos.total / total_usuarios.total * 100), 2) if total_usuarios.total > 0 else 0,
            "pendientes_pago": pendientes_pago.total,
            "registros_hoy": nuevos_registros_hoy.total,
            "nuevos_registros_hoy": nuevos_registros_hoy.total,
            "empresas_activas": empresas_activas.total,
            "empleados_activos": empleados_activos.total,
            "popularidad_planes": [{"plan": row.nombre, "suscriptores": row.suscriptores} for row in planes],
            "revenue_por_plan": [
                {"plan": row.nombre, "suscriptores": row.suscriptores, "revenue": float(row.revenue)}
                for row in revenue_por_plan
            ],
            "ultimas_suscripciones": [
                {
                    "id": row.id,
                    "usuario_nombre": row.usuario_nombre,
                    "usuario_email": row.usuario_email,
                    "plan_nombre": row.plan_nombre,
                    "estado": row.estado,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in ultimas_suscripciones
            ],
            "ultimas_actividades": [
                {
                    "accion": row.accion,
                    "tabla_afectada": row.tabla_afectada,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in ultimas_actividades
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
