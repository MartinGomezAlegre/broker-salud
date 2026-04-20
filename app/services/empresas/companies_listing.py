import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.empresas import EmpresaCrear
from app.services.empresas.common import empresa_to_dict

logger = logging.getLogger(__name__)


def listar_empresas(
    db: Session,
    activo: bool | None,
    buscar: str | None,
    limit: int,
    offset: int,
):
    try:
        condiciones = []
        params: dict = {"limit": limit, "offset": offset}
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
            {where}
            GROUP BY e.id, e.razon_social, e.cuit, e.nombre_comercial, e.rubro,
                     e.direccion, e.localidad, e.provincia, e.responsabilidad_iva,
                     e.email_contacto, e.contacto_nombre, e.contacto_cargo, e.telefono,
                     e.activo, e.created_at,
                     se.estado, se.plan_id, p.nombre, se.precio_por_empleado, se.precio_total,
                     se.periodicidad, se.fecha_inicio, se.fecha_fin, se.proximo_cobro
        """

        total = db.execute(text(f"SELECT COUNT(*) FROM (SELECT e.id {base_query}) empresas_paginadas"), params).scalar() or 0
        rows = db.execute(text(f"""
            SELECT e.id, e.razon_social, e.cuit, e.nombre_comercial, e.rubro,
                   e.direccion, e.localidad, e.provincia, e.responsabilidad_iva,
                   e.email_contacto, e.contacto_nombre, e.contacto_cargo, e.telefono,
                   e.activo, e.created_at,
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
                "activo": row.activo,
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
        existente = db.execute(
            text("SELECT id FROM empresas WHERE cuit = :cuit"),
            {"cuit": datos.cuit},
        ).fetchone()
        if existente:
            raise HTTPException(status_code=400, detail="Ya existe una empresa con ese CUIT")

        result = db.execute(text("""
            INSERT INTO empresas
              (razon_social, cuit, nombre_comercial, rubro, direccion, localidad,
               provincia, responsabilidad_iva, telefono, email_contacto, contacto_nombre, contacto_cargo, activo)
            VALUES
              (:razon_social, :cuit, :nombre_comercial, :rubro, :direccion, :localidad,
               :provincia, :responsabilidad_iva, :telefono, :email_contacto, :contacto_nombre, :contacto_cargo, true)
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
