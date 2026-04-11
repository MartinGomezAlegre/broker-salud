from datetime import date
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.empresas import CambiarEstadoSuscripcionEmpresarial, ESTADOS_SUSCRIPCION_EMPRESA, SuscripcionEmpresarialCrear
from app.services.empresas.common import calcular_fecha_fin

logger = logging.getLogger(__name__)


def crear_suscripcion_empresarial(db: Session, empresa_id: int, datos: SuscripcionEmpresarialCrear):
    try:
        empresa = db.execute(
            text("SELECT id FROM empresas WHERE id = :id"),
            {"id": empresa_id},
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        if datos.periodicidad not in ("mensual", "trimestral", "anual"):
            raise HTTPException(status_code=400, detail="Periodicidad inválida. Usar: mensual, trimestral, anual")

        fecha_fin = calcular_fecha_fin(datos.fecha_inicio, datos.periodicidad)
        precio_total = datos.cantidad_empleados * datos.precio_por_empleado

        result = db.execute(text("""
            INSERT INTO suscripciones_empresariales
              (empresa_id, plan_id, cantidad_empleados, precio_por_empleado,
               precio_total, periodicidad, fecha_inicio, fecha_fin,
               proximo_cobro, estado)
            VALUES
              (:empresa_id, :plan_id, :cantidad_empleados, :precio_por_empleado,
               :precio_total, :periodicidad, :fecha_inicio, :fecha_fin,
               :proximo_cobro, 'activa')
            RETURNING id
        """), {
            "empresa_id": empresa_id,
            "plan_id": datos.plan_id,
            "cantidad_empleados": datos.cantidad_empleados,
            "precio_por_empleado": datos.precio_por_empleado,
            "precio_total": precio_total,
            "periodicidad": datos.periodicidad,
            "fecha_inicio": datos.fecha_inicio,
            "fecha_fin": fecha_fin,
            "proximo_cobro": fecha_fin,
        }).fetchone()
        db.commit()

        suscripcion = db.execute(
            text("SELECT * FROM suscripciones_empresariales WHERE id = :id"),
            {"id": result.id},
        ).fetchone()

        return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in suscripcion._mapping.items()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def cambiar_estado_suscripcion_empresarial(
    db: Session,
    empresa_id: int,
    datos: CambiarEstadoSuscripcionEmpresarial,
):
    try:
        if datos.estado not in ESTADOS_SUSCRIPCION_EMPRESA:
            raise HTTPException(status_code=400, detail=f"Estado inválido. Permitidos: {', '.join(ESTADOS_SUSCRIPCION_EMPRESA)}")

        suscripcion = db.execute(text("""
            SELECT id, estado FROM suscripciones_empresariales
            WHERE empresa_id = :id
            ORDER BY created_at DESC LIMIT 1
        """), {"id": empresa_id}).fetchone()
        if not suscripcion:
            raise HTTPException(status_code=404, detail="Suscripción empresarial no encontrada")

        estado_anterior = suscripcion.estado
        db.execute(
            text("UPDATE suscripciones_empresariales SET estado = :estado WHERE id = :id"),
            {"estado": datos.estado, "id": suscripcion.id},
        )

        if datos.estado in ("cancelada", "vencida"):
            db.execute(
                text("UPDATE empleados_empresa SET activo = false WHERE empresa_id = :id"),
                {"id": empresa_id},
            )
        elif datos.estado == "activa":
            db.execute(
                text("""UPDATE empleados_empresa SET activo = true, fecha_baja = null
                        WHERE empresa_id = :id"""),
                {"id": empresa_id},
            )

        db.execute(text("""
            INSERT INTO historial_suscripciones
              (suscripcion_id, campo_modificado, valor_anterior, valor_nuevo, motivo)
            VALUES (:sid, 'estado', :anterior, :nuevo, :motivo)
        """), {
            "sid": suscripcion.id,
            "anterior": estado_anterior,
            "nuevo": datos.estado,
            "motivo": datos.motivo,
        })
        db.commit()

        actualizada = db.execute(
            text("SELECT * FROM suscripciones_empresariales WHERE id = :id"),
            {"id": suscripcion.id},
        ).fetchone()
        return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in actualizada._mapping.items()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def ver_suscripcion_empresarial(db: Session, empresa_id: int):
    try:
        row = db.execute(text("""
            SELECT se.id, p.nombre AS plan_nombre,
                   se.cantidad_empleados, se.precio_por_empleado, se.precio_total,
                   se.estado, se.periodicidad, se.fecha_inicio, se.fecha_fin,
                   se.proximo_cobro
            FROM suscripciones_empresariales se
            LEFT JOIN planes p ON p.id = se.plan_id
            WHERE se.empresa_id = :id
            ORDER BY se.created_at DESC LIMIT 1
        """), {"id": empresa_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Sin suscripción registrada")

        dias_para_vencer = None
        if row.fecha_fin:
            dias_para_vencer = (row.fecha_fin - date.today()).days

        return {
            "id": row.id,
            "plan_nombre": row.plan_nombre,
            "cantidad_empleados": row.cantidad_empleados,
            "precio_por_empleado": float(row.precio_por_empleado) if row.precio_por_empleado else None,
            "precio_total": float(row.precio_total) if row.precio_total else None,
            "estado": row.estado,
            "periodicidad": row.periodicidad,
            "fecha_inicio": row.fecha_inicio.isoformat() if row.fecha_inicio else None,
            "fecha_fin": row.fecha_fin.isoformat() if row.fecha_fin else None,
            "proximo_cobro": row.proximo_cobro.isoformat() if row.proximo_cobro else None,
            "dias_para_vencer": dias_para_vencer,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
