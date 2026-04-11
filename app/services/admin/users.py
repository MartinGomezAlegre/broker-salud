import json
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.admin import CambiarEstadoUsuario

logger = logging.getLogger(__name__)


def listar_usuarios(
    db: Session,
    buscar: str | None,
    limit: int,
    offset: int,
):
    try:
        params: dict = {"limit": limit, "offset": offset}
        if buscar:
            params["q"] = f"%{buscar}%"
            rows = db.execute(text("""
                SELECT id, nombre, apellido, email, telefono, dni,
                       fecha_nacimiento, rol, activo, created_at,
                       plan_nombre, estado_suscripcion
                FROM (
                    SELECT u.id, u.nombre, u.apellido, u.email, u.telefono, u.dni,
                           u.fecha_nacimiento, u.rol, u.activo, u.created_at,
                           sub.plan_nombre, sub.estado_suscripcion
                    FROM usuarios u
                    LEFT JOIN LATERAL (
                        SELECT p.nombre AS plan_nombre,
                               s.estado AS estado_suscripcion
                        FROM suscripciones s
                        JOIN planes p ON p.id = s.plan_id
                        WHERE s.usuario_id = u.id
                        ORDER BY
                            CASE s.estado
                                WHEN 'activa' THEN 1
                                WHEN 'pendiente_pago' THEN 2
                                ELSE 3
                            END,
                            COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                            s.created_at DESC
                        LIMIT 1
                    ) sub ON true
                ) usuarios_con_suscripcion
                WHERE nombre ILIKE :q OR apellido ILIKE :q OR email ILIKE :q
                ORDER BY created_at DESC LIMIT :limit OFFSET :offset
            """), params).fetchall()
        else:
            rows = db.execute(text("""
                SELECT id, nombre, apellido, email, telefono, dni,
                       fecha_nacimiento, rol, activo, created_at,
                       plan_nombre, estado_suscripcion
                FROM (
                    SELECT u.id, u.nombre, u.apellido, u.email, u.telefono, u.dni,
                           u.fecha_nacimiento, u.rol, u.activo, u.created_at,
                           sub.plan_nombre, sub.estado_suscripcion
                    FROM usuarios u
                    LEFT JOIN LATERAL (
                        SELECT p.nombre AS plan_nombre,
                               s.estado AS estado_suscripcion
                        FROM suscripciones s
                        JOIN planes p ON p.id = s.plan_id
                        WHERE s.usuario_id = u.id
                        ORDER BY
                            CASE s.estado
                                WHEN 'activa' THEN 1
                                WHEN 'pendiente_pago' THEN 2
                                ELSE 3
                            END,
                            COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                            s.created_at DESC
                        LIMIT 1
                    ) sub ON true
                ) usuarios_con_suscripcion
                ORDER BY created_at DESC LIMIT :limit OFFSET :offset
            """), params).fetchall()

        return [
            {
                "id": row.id,
                "nombre": row.nombre,
                "apellido": row.apellido,
                "email": row.email,
                "telefono": row.telefono,
                "dni": row.dni if row.dni is not None else "",
                "fecha_nacimiento": row.fecha_nacimiento.isoformat() if row.fecha_nacimiento else None,
                "rol": row.rol,
                "activo": row.activo,
                "plan_nombre": row.plan_nombre,
                "estado_suscripcion": row.estado_suscripcion,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def detalle_usuario(db: Session, target_usuario_id: int):
    try:
        usuario = db.execute(text("""
            SELECT u.id, u.nombre, u.apellido, u.email, u.telefono, u.dni,
                   u.fecha_nacimiento, u.cuit, u.direccion, u.localidad,
                   u.codigo_postal, u.provincia, u.pais, u.rol, u.activo, u.created_at,
                   sub.suscripcion_id, sub.plan_id, sub.plan_nombre,
                   sub.estado_suscripcion, sub.fecha_inicio_suscripcion,
                   sub.fecha_vencimiento, sub.max_beneficiarios
            FROM usuarios u
            LEFT JOIN LATERAL (
                SELECT s.id AS suscripcion_id,
                       s.plan_id,
                       p.nombre AS plan_nombre,
                       s.estado AS estado_suscripcion,
                       s.fecha_inicio AS fecha_inicio_suscripcion,
                       s.fecha_vencimiento,
                       p.max_beneficiarios
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                WHERE s.usuario_id = u.id
                ORDER BY
                    CASE s.estado
                        WHEN 'activa' THEN 1
                        WHEN 'pendiente_pago' THEN 2
                        ELSE 3
                    END,
                    COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                    s.created_at DESC
                LIMIT 1
            ) sub ON true
            WHERE u.id = :usuario_id
        """), {"usuario_id": target_usuario_id}).fetchone()

        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        beneficiarios_rows = []
        if usuario.suscripcion_id:
            beneficiarios_rows = db.execute(text("""
                SELECT id, nombre, apellido, dni, fecha_nacimiento, relacion
                FROM beneficiarios
                WHERE suscripcion_id = :suscripcion_id
                ORDER BY created_at ASC
            """), {"suscripcion_id": usuario.suscripcion_id}).fetchall()

        return {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "telefono": usuario.telefono,
            "dni": usuario.dni if usuario.dni is not None else "",
            "fecha_nacimiento": usuario.fecha_nacimiento.isoformat() if usuario.fecha_nacimiento else None,
            "cuit": usuario.cuit,
            "direccion": usuario.direccion,
            "localidad": usuario.localidad,
            "codigo_postal": usuario.codigo_postal,
            "provincia": usuario.provincia,
            "pais": usuario.pais,
            "rol": usuario.rol,
            "activo": usuario.activo,
            "created_at": usuario.created_at.isoformat() if usuario.created_at else None,
            "suscripcion_id": usuario.suscripcion_id,
            "plan_id": usuario.plan_id,
            "plan_nombre": usuario.plan_nombre,
            "estado_suscripcion": usuario.estado_suscripcion,
            "fecha_inicio_suscripcion": usuario.fecha_inicio_suscripcion.isoformat() if usuario.fecha_inicio_suscripcion else None,
            "fecha_vencimiento": usuario.fecha_vencimiento.isoformat() if usuario.fecha_vencimiento else None,
            "max_beneficiarios": usuario.max_beneficiarios,
            "beneficiarios": [
                {
                    "id": item.id,
                    "nombre": item.nombre,
                    "apellido": item.apellido,
                    "dni": item.dni,
                    "fecha_nacimiento": item.fecha_nacimiento.isoformat() if item.fecha_nacimiento else None,
                    "relacion": item.relacion,
                }
                for item in beneficiarios_rows
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def cambiar_estado_usuario(
    db: Session,
    usuario_id: int,
    datos: CambiarEstadoUsuario,
):
    try:
        usuario = db.execute(
            text("SELECT id, nombre, apellido, email, activo, rol FROM usuarios WHERE id = :id"),
            {"id": usuario_id},
        ).fetchone()

        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        estado_anterior = usuario.activo

        db.execute(
            text("UPDATE usuarios SET activo = :activo WHERE id = :id"),
            {"activo": datos.activo, "id": usuario_id},
        )

        accion = "dar_de_alta" if datos.activo else "dar_de_baja"
        db.execute(text("""
            INSERT INTO auditoria (accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos)
            VALUES (:accion, 'usuarios', :registro_id, :datos_anteriores, :datos_nuevos)
        """), {
            "accion": accion,
            "registro_id": usuario_id,
            "datos_anteriores": json.dumps({"activo": estado_anterior}),
            "datos_nuevos": json.dumps({"activo": datos.activo, "motivo": datos.motivo}),
        })

        db.commit()

        return {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "activo": datos.activo,
            "rol": usuario.rol,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
