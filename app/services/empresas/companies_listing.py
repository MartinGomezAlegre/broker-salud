import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.empresas import EmpresaCrear
from app.services.comercial.accounts import create_commercial_user
from app.services.empresas.access import aplicar_scope_empresas
from app.services.empresas.common import empresa_to_dict

logger = logging.getLogger(__name__)


def listar_empresas(
    db: Session,
    activo: bool | None,
    buscar: str | None,
    limit: int,
    offset: int,
    viewer_user_id: int,
):
    try:
        condiciones = []
        params: dict = {"limit": limit, "offset": offset}
        aplicar_scope_empresas(db, condiciones, params, viewer_user_id)
        if activo is not None:
            condiciones.append("e.activo = :activo")
            params["activo"] = activo
        if buscar:
            condiciones.append("(e.razon_social ILIKE :q OR e.cuit ILIKE :q OR e.email_contacto ILIKE :q)")
            params["q"] = f"%{buscar}%"

        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
        base_query = f"""
            FROM empresas e
            LEFT JOIN empleados_empresa em ON em.empresa_id = e.id
            LEFT JOIN suscripciones_empresariales se
                   ON se.empresa_id = e.id AND se.estado NOT IN ('cancelada', 'vencida')
            LEFT JOIN planes p ON p.id = se.plan_id
            LEFT JOIN usuarios admin_u ON admin_u.id = e.admin_user_id
            {where}
            GROUP BY e.id, e.razon_social, e.cuit, e.nombre_comercial, e.rubro,
                     e.direccion, e.localidad, e.provincia, e.responsabilidad_iva,
                     e.email_contacto, e.contacto_nombre, e.contacto_cargo, e.telefono, e.admin_user_id,
                     e.activo, e.created_at, e.visible_para_gestores,
                     admin_u.id, admin_u.nombre, admin_u.apellido, admin_u.email,
                     se.estado, se.plan_id, p.nombre, se.precio_por_empleado, se.precio_total,
                     se.periodicidad, se.fecha_inicio, se.fecha_fin, se.proximo_cobro
        """

        total = db.execute(text(f"SELECT COUNT(*) FROM (SELECT e.id {base_query}) empresas_paginadas"), params).scalar() or 0
        rows = db.execute(text(f"""
            SELECT e.id, e.razon_social, e.cuit, e.nombre_comercial, e.rubro,
                   e.direccion, e.localidad, e.provincia, e.responsabilidad_iva,
                   e.email_contacto, e.contacto_nombre, e.contacto_cargo, e.telefono,
                   e.activo, e.created_at, e.visible_para_gestores,
                   admin_u.id AS admin_user_id,
                   admin_u.nombre AS admin_nombre,
                   admin_u.apellido AS admin_apellido,
                   admin_u.email AS admin_access_email,
                   COUNT(em.id) FILTER (WHERE em.activo = true) AS empleados_activos,
                   COUNT(em.id) AS cantidad_empleados,
                   se.estado AS estado_suscripcion,
                   se.plan_id,
                   p.nombre AS plan_nombre,
                   se.precio_por_empleado,
                   se.precio_total,
                   se.periodicidad,
                   se.fecha_inicio AS fecha_inicio_suscripcion,
                   COALESCE(se.fecha_fin, se.proximo_cobro) AS fecha_vencimiento
            {base_query}
            ORDER BY e.created_at DESC LIMIT :limit OFFSET :offset
        """), params).fetchall()

        items = [
            {
                "id": row.id,
                "razon_social": row.razon_social,
                "cuit": row.cuit,
                "nombre_comercial": row.nombre_comercial,
                "rubro": row.rubro,
                "direccion": row.direccion,
                "localidad": row.localidad,
                "provincia": row.provincia,
                "responsabilidad_iva": row.responsabilidad_iva,
                "contacto_email": row.email_contacto,
                "contacto_nombre": row.contacto_nombre,
                "contacto_cargo": row.contacto_cargo,
                "contacto_telefono": row.telefono,
                "admin_user_id": row.admin_user_id,
                "admin_access_email": row.admin_access_email,
                "admin_access_name": " ".join(part for part in [row.admin_nombre, row.admin_apellido] if part).strip() or None,
                "activo": row.activo,
                "visible_para_gestores": bool(row.visible_para_gestores),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "empleados_activos": row.empleados_activos or 0,
                "cantidad_empleados": row.cantidad_empleados or 0,
                "estado_suscripcion": row.estado_suscripcion,
                "plan_id": row.plan_id,
                "plan_nombre": row.plan_nombre,
                "precio_por_empleado": float(row.precio_por_empleado) if row.precio_por_empleado is not None else None,
                "precio_total": float(row.precio_total) if row.precio_total is not None else None,
                "periodicidad": row.periodicidad,
                "fecha_inicio_suscripcion": row.fecha_inicio_suscripcion.isoformat() if row.fecha_inicio_suscripcion else None,
                "fecha_vencimiento": row.fecha_vencimiento.isoformat() if row.fecha_vencimiento else None,
            }
            for row in rows
        ]
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def crear_empresa(db: Session, datos: EmpresaCrear):
    try:
        admin_access_email = _clean_optional(datos.admin_access_email)
        admin_access_password = _clean_optional(datos.admin_access_password)
        if bool(admin_access_email) != bool(admin_access_password):
            raise HTTPException(
                status_code=400,
                detail="Para crear el acceso empresa_admin necesitas email y contrasena inicial.",
            )

        existente = db.execute(
            text("SELECT id FROM empresas WHERE cuit = :cuit"),
            {"cuit": datos.cuit},
        ).fetchone()
        if existente:
            raise HTTPException(status_code=400, detail="Ya existe una empresa con ese CUIT")

        admin_user_id = None
        if admin_access_email and admin_access_password:
            admin_user_id = create_commercial_user(
                db,
                full_name=datos.contacto_nombre,
                email=admin_access_email,
                password=admin_access_password,
                role="empresa_admin",
            )

        result = db.execute(text("""
            INSERT INTO empresas
              (razon_social, cuit, nombre_comercial, rubro, direccion, localidad,
               provincia, responsabilidad_iva, telefono, email_contacto, contacto_nombre, contacto_cargo,
               admin_user_id, activo, visible_para_gestores)
            VALUES
              (:razon_social, :cuit, :nombre_comercial, :rubro, :direccion, :localidad,
               :provincia, :responsabilidad_iva, :telefono, :email_contacto, :contacto_nombre, :contacto_cargo,
               :admin_user_id, true, :visible_para_gestores)
            RETURNING id
        """), {
            "razon_social": datos.razon_social,
            "cuit": datos.cuit,
            "nombre_comercial": datos.nombre_comercial,
            "rubro": datos.rubro,
            "direccion": datos.direccion,
            "localidad": datos.localidad,
            "provincia": datos.provincia,
            "responsabilidad_iva": datos.responsabilidad_iva,
            "telefono": datos.telefono,
            "email_contacto": datos.email_contacto,
            "contacto_nombre": datos.contacto_nombre,
            "contacto_cargo": datos.contacto_cargo,
            "admin_user_id": admin_user_id,
            "visible_para_gestores": datos.visible_para_gestores,
        }).fetchone()
        db.commit()

        empresa = db.execute(
            text("SELECT * FROM empresas WHERE id = :id"),
            {"id": result.id},
        ).fetchone()
        return empresa_to_dict(empresa)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
