import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def obtener_alertas(db: Session):
    try:
        pendientes = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones WHERE estado = 'pendiente_pago'
        """)).fetchone().total
        sin_convertir = db.execute(text("""
            SELECT COUNT(*) as total FROM usuarios
            WHERE activo = true
              AND created_at <= NOW() - INTERVAL '7 days'
              AND NOT EXISTS (
                  SELECT 1
                  FROM suscripciones s
                  WHERE s.usuario_id = usuarios.id
                    AND s.estado IN ('activa', 'cancelacion_programada', 'pendiente_pago')
              )
        """)).fetchone().total
        exportar_mediquo = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE DATE(created_at) = CURRENT_DATE
        """)).fetchone().total
        empresas_vencimiento = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones_empresariales
            WHERE estado NOT IN ('cancelada', 'vencida')
              AND proximo_cobro BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
        """)).fetchone().total
        empresas_pendiente = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones_empresariales
            WHERE estado = 'pendiente_pago'
        """)).fetchone().total
        vencidas_3dias = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE estado = 'pendiente_pago'
              AND created_at <= NOW() - INTERVAL '3 days'
        """)).fetchone().total
        vencen_semana = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE estado IN ('activa', 'cancelacion_programada')
              AND fecha_vencimiento BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
        """)).fetchone().total

        alertas = []
        if pendientes > 0:
            alertas.append({
                "tipo": "pendientes_pago",
                "cantidad": pendientes,
                "mensaje": f"{pendientes} suscripciones pendientes de pago",
            })
        if sin_convertir > 0:
            alertas.append({
                "tipo": "sin_convertir",
                "cantidad": sin_convertir,
                "mensaje": f"{sin_convertir} usuarios sin suscripcion hace mas de 7 dias",
            })
        if exportar_mediquo > 0:
            alertas.append({
                "tipo": "exportar_mediquo",
                "cantidad": exportar_mediquo,
                "mensaje": f"{exportar_mediquo} nuevos suscriptores para exportar a Mediquo hoy",
            })
        if empresas_vencimiento > 0:
            alertas.append({
                "tipo": "empresas_vencimiento_7_dias",
                "cantidad": empresas_vencimiento,
                "mensaje": f"{empresas_vencimiento} empresas vencen en los proximos 7 dias",
            })
        if empresas_pendiente > 0:
            alertas.append({
                "tipo": "empresas_pendiente_pago",
                "cantidad": empresas_pendiente,
                "mensaje": f"{empresas_pendiente} empresas con pago pendiente",
            })
        if vencidas_3dias > 0:
            alertas.append({
                "tipo": "suscripciones_vencidas_3dias",
                "cantidad": vencidas_3dias,
                "mensaje": f"{vencidas_3dias} suscripciones pendientes hace mas de 3 dias",
            })
        if vencen_semana > 0:
            alertas.append({
                "tipo": "vencen_esta_semana",
                "cantidad": vencen_semana,
                "mensaje": f"{vencen_semana} suscripciones activas vencen en los proximos 7 dias",
            })

        return alertas
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
