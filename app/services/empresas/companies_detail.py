from datetime import date
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.empresas.common import empleado_to_dict, empresa_to_dict, serialize_value

logger = logging.getLogger(__name__)


def detalle_empresa(db: Session, empresa_id: int):
    try:
        empresa = db.execute(
            text("SELECT * FROM empresas WHERE id = :id"),
            {"id": empresa_id},
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        admin_access = None
        if empresa.admin_user_id:
            admin_access = db.execute(
                text(
                    """
                    SELECT id, nombre, apellido, email
                    FROM usuarios
                    WHERE id = :id
                    """
                ),
                {"id": empresa.admin_user_id},
            ).fetchone()

        suscripcion = db.execute(text("""
            SELECT se.*, p.nombre AS plan_nombre
            FROM suscripciones_empresariales se
            LEFT JOIN planes p ON p.id = se.plan_id
            WHERE se.empresa_id = :id
            ORDER BY se.created_at DESC LIMIT 1
        """), {"id": empresa_id}).fetchone()

        empleados = db.execute(text("""
            SELECT id, nombre, apellido, dni, email, cargo, telefono,
                   activo, fecha_alta, fecha_baja, usuario_id
            FROM empleados_empresa
            WHERE empresa_id = :id
            ORDER BY fecha_alta DESC
        """), {"id": empresa_id}).fetchall()

        auditoria = db.execute(text("""
            SELECT accion, created_at
            FROM auditoria
            WHERE (tabla_afectada = 'empresas' AND registro_id = :id)
               OR (tabla_afectada = 'empleados_empresa' AND registro_id IN (
                    SELECT id FROM empleados_empresa WHERE empresa_id = :id
               ))
            ORDER BY created_at DESC
            LIMIT 50
        """), {"id": empresa_id}).fetchall()

        empleados_activos = sum(1 for empleado in empleados if empleado.activo)
        meses_activa = _meses_activa(suscripcion.fecha_inicio if suscripcion else None)
        proximo_vencimiento = suscripcion.fecha_fin.isoformat() if suscripcion and suscripcion.fecha_fin else None

        empresa_payload = {
            "id": empresa.id,
            "razon_social": empresa.razon_social,
            "nombre_comercial": empresa.nombre_comercial,
            "cuit": empresa.cuit,
            "rubro": empresa.rubro,
            "direccion": empresa.direccion,
            "localidad": empresa.localidad,
            "provincia": empresa.provincia,
            "responsabilidad_iva": empresa.responsabilidad_iva,
            "contacto_nombre": empresa.contacto_nombre,
            "contacto_cargo": empresa.contacto_cargo,
            "contacto_email": empresa.email_contacto,
            "contacto_telefono": empresa.telefono,
            "visible_para_gestores": bool(getattr(empresa, "visible_para_gestores", False)),
            "admin_user_id": empresa.admin_user_id,
            "admin_access_email": admin_access.email if admin_access else None,
            "admin_access_name": " ".join(
                part for part in [admin_access.nombre if admin_access else None, admin_access.apellido if admin_access else None] if part
            ).strip() or None,
            "activo": empresa.activo,
            "created_at": serialize_value(empresa.created_at),
            "plan_nombre": suscripcion.plan_nombre if suscripcion else None,
            "plan_id": suscripcion.plan_id if suscripcion else None,
            "cantidad_empleados": suscripcion.cantidad_empleados if suscripcion and suscripcion.cantidad_empleados is not None else len(empleados),
            "precio_por_empleado": float(suscripcion.precio_por_empleado) if suscripcion and suscripcion.precio_por_empleado is not None else None,
            "precio_total": float(suscripcion.precio_total) if suscripcion and suscripcion.precio_total is not None else None,
            "periodicidad": suscripcion.periodicidad if suscripcion else None,
            "estado_suscripcion": suscripcion.estado if suscripcion else None,
            "fecha_inicio_suscripcion": serialize_value(suscripcion.fecha_inicio) if suscripcion else None,
            "fecha_vencimiento": serialize_value(suscripcion.fecha_fin) if suscripcion and suscripcion.fecha_fin else proximo_vencimiento,
            "empleados_activos": empleados_activos,
            "empleados_total": len(empleados),
            "auditoria": [
                {
                    "descripcion": item.accion.replace("_", " ").capitalize(),
                    "fecha": serialize_value(item.created_at),
                }
                for item in auditoria
            ],
        }

        return {
            **empresa_payload,
            "empresa": empresa_to_dict(empresa),
            "suscripcion": {key: serialize_value(value) for key, value in suscripcion._mapping.items()} if suscripcion else None,
            "empleados": [empleado_to_dict(empleado) for empleado in empleados],
            "metricas": {
                "empleados_activos": empleados_activos,
                "empleados_totales": len(empleados),
                "meses_activa": meses_activa,
                "proximo_vencimiento": proximo_vencimiento,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def _meses_activa(fecha_inicio) -> int:
    if not fecha_inicio:
        return 0
    delta = date.today() - fecha_inicio
    return delta.days // 30
