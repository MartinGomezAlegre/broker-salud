from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.auth import get_current_user

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)

@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    # MRR — ingresos mensuales recurrentes
    mrr = db.execute(text("""
        SELECT COALESCE(SUM(precio_pagado), 0) as mrr
        FROM suscripciones
        WHERE estado = 'activa'
    """)).fetchone()

    # Total suscriptores activos
    activos = db.execute(text("""
        SELECT COUNT(*) as total
        FROM suscripciones
        WHERE estado = 'activa'
    """)).fetchone()

    # Nuevas suscripciones esta semana
    nuevas_semana = db.execute(text("""
        SELECT COUNT(*) as total
        FROM suscripciones
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """)).fetchone()

    # Cancelaciones este mes
    cancelaciones = db.execute(text("""
        SELECT COUNT(*) as total
        FROM suscripciones
        WHERE estado = 'cancelada'
        AND created_at >= DATE_TRUNC('month', NOW())
    """)).fetchone()

    # Total usuarios registrados
    total_usuarios = db.execute(text("""
        SELECT COUNT(*) as total FROM usuarios
    """)).fetchone()

    # Usuarios sin suscripción activa (no convirtieron)
    sin_suscripcion = db.execute(text("""
        SELECT COUNT(*) as total FROM usuarios
        WHERE id NOT IN (
            SELECT usuario_id FROM suscripciones
            WHERE estado = 'activa'
        )
    """)).fetchone()

    # Churn rate este mes
    total_mes_anterior = db.execute(text("""
        SELECT COUNT(*) as total FROM suscripciones
        WHERE created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
        AND created_at < DATE_TRUNC('month', NOW())
    """)).fetchone()

    churn_rate = 0
    if total_mes_anterior.total > 0:
        churn_rate = round((cancelaciones.total / total_mes_anterior.total) * 100, 2)

    # Popularidad de planes
    planes = db.execute(text("""
        SELECT p.nombre, COUNT(s.id) as suscriptores
        FROM planes p
        LEFT JOIN suscripciones s ON p.id = s.plan_id AND s.estado = 'activa'
        GROUP BY p.nombre
        ORDER BY suscriptores DESC
    """)).fetchall()

    return {
        "mrr": float(mrr.mrr),
        "suscriptores_activos": activos.total,
        "nuevas_suscripciones_semana": nuevas_semana.total,
        "cancelaciones_mes": cancelaciones.total,
        "churn_rate_porcentaje": churn_rate,
        "total_usuarios": total_usuarios.total,
        "usuarios_sin_convertir": sin_suscripcion.total,
        "tasa_conversion": round((activos.total / total_usuarios.total * 100), 2) if total_usuarios.total > 0 else 0,
        "popularidad_planes": [{"plan": p.nombre, "suscriptores": p.suscriptores} for p in planes]
    }