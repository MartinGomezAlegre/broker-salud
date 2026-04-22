import json
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import hashear_password
from app.schemas.admin import PersonalActualizar, PersonalCrear

logger = logging.getLogger(__name__)

PERSONAL_ROLES = {"admin", "gestor_interno"}


def listar_personal(
    db: Session,
    buscar: str | None,
    filtro: str | None,
    limit: int,
    offset: int,
):
    try:
        params: dict = {"limit": limit, "offset": offset}
        condiciones = ["u.rol IN ('admin', 'gestor_interno')"]

        if buscar:
            params["q"] = f"%{buscar.strip()}%"
            condiciones.append(
                """
                (
                    u.nombre ILIKE :q OR
                    u.apellido ILIKE :q OR
                    u.email ILIKE :q OR
                    p.area ILIKE :q OR
                    p.cargo ILIKE :q OR
                    e.razon_social ILIKE :q
                )
                """
            )

        if filtro == "activos":
            condiciones.append("u.activo = true")
        elif filtro == "inactivos":
            condiciones.append("u.activo = false")
        elif filtro == "admins":
            condiciones.append("u.rol = 'admin'")
        elif filtro == "gestores":
            condiciones.append("u.rol = 'gestor_interno'")

        where_clause = " AND ".join(condiciones)

        total = db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT u.id
                    FROM usuarios u
                    LEFT JOIN personal_interno p ON p.usuario_id = u.id
                    LEFT JOIN gestor_empresas_permitidas gep ON gep.usuario_id = u.id
                    LEFT JOIN empresas e ON e.id = gep.empresa_id
                    WHERE {where_clause}
                    GROUP BY u.id
                ) personal_filtrado
                """
            ),
            params,
        ).scalar() or 0

        rows = db.execute(
            text(
                f"""
                SELECT
                    u.id,
                    u.nombre,
                    u.apellido,
                    u.email,
                    u.telefono,
                    u.rol,
                    u.activo,
                    u.created_at,
                    p.area,
                    p.cargo,
                    p.responsabilidades,
                    p.updated_at AS perfil_updated_at,
                    COUNT(DISTINCT gep.empresa_id) AS empresas_visibles_count,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT e.razon_social), NULL) AS empresas_visibles,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT gep.empresa_id), NULL) AS empresa_ids
                FROM usuarios u
                LEFT JOIN personal_interno p ON p.usuario_id = u.id
                LEFT JOIN gestor_empresas_permitidas gep ON gep.usuario_id = u.id
                LEFT JOIN empresas e ON e.id = gep.empresa_id
                WHERE {where_clause}
                GROUP BY
                    u.id,
                    u.nombre,
                    u.apellido,
                    u.email,
                    u.telefono,
                    u.rol,
                    u.activo,
                    u.created_at,
                    p.area,
                    p.cargo,
                    p.responsabilidades,
                    p.updated_at
                ORDER BY u.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()

        items = [
            {
                "id": row.id,
                "nombre": row.nombre,
                "apellido": row.apellido,
                "email": row.email,
                "telefono": row.telefono,
                "rol": row.rol,
                "activo": row.activo,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "area": row.area,
                "cargo": row.cargo,
                "responsabilidades": row.responsabilidades,
                "perfil_updated_at": row.perfil_updated_at.isoformat() if row.perfil_updated_at else None,
                "empresas_visibles_count": row.empresas_visibles_count or 0,
                "empresas_visibles": list(row.empresas_visibles or []),
                "empresa_ids": [empresa_id for empresa_id in list(row.empresa_ids or []) if empresa_id is not None],
            }
            for row in rows
        ]
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def crear_personal(
    db: Session,
    datos: PersonalCrear,
    actor_user_id: int,
):
    try:
        rol = _normalizar_rol(datos.rol)
        existe = db.execute(
            text("SELECT id FROM usuarios WHERE email = :email"),
            {"email": str(datos.email)},
        ).fetchone()
        if existe:
            raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email.")

        user_row = db.execute(
            text(
                """
                INSERT INTO usuarios (
                    nombre, apellido, email, telefono, password_hash, rol, activo
                )
                VALUES (
                    :nombre, :apellido, :email, :telefono, :password_hash, :rol, true
                )
                RETURNING id, nombre, apellido, email, telefono, rol, activo, created_at
                """
            ),
            {
                "nombre": datos.nombre.strip(),
                "apellido": datos.apellido.strip(),
                "email": str(datos.email).lower(),
                "telefono": datos.telefono,
                "password_hash": hashear_password(datos.contrasenia),
                "rol": rol,
            },
        ).fetchone()

        db.execute(
            text(
                """
                INSERT INTO personal_interno (
                    usuario_id, area, cargo, responsabilidades
                )
                VALUES (
                    :usuario_id, :area, :cargo, :responsabilidades
                )
                """
            ),
            {
                "usuario_id": user_row.id,
                "area": datos.area,
                "cargo": datos.cargo,
                "responsabilidades": datos.responsabilidades,
            },
        )
        _sincronizar_empresas_visibles(
            db,
            usuario_id=user_row.id,
            rol=rol,
            empresa_ids=datos.empresa_ids,
        )

        db.execute(
            text(
                """
                INSERT INTO auditoria (accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos)
                VALUES (:accion, 'usuarios', :registro_id, :datos_anteriores, :datos_nuevos)
                """
            ),
            {
                "accion": "crear_personal_interno",
                "registro_id": user_row.id,
                "datos_anteriores": json.dumps({}),
                "datos_nuevos": json.dumps(
                    {
                        "rol": rol,
                        "area": datos.area,
                        "cargo": datos.cargo,
                        "empresa_ids": datos.empresa_ids,
                        "actor_user_id": actor_user_id,
                    }
                ),
            },
        )

        db.commit()
        return _fetch_personal_item(db, user_row.id)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_personal(
    db: Session,
    usuario_id: int,
    datos: PersonalActualizar,
    actor_user_id: int,
):
    try:
        actual = _fetch_personal_row(db, usuario_id)
        if not actual:
            raise HTTPException(status_code=404, detail="Personal no encontrado.")

        nuevo_rol = _normalizar_rol(datos.rol) if datos.rol is not None else actual.rol
        if actor_user_id == usuario_id and actual.rol == "admin" and nuevo_rol != "admin":
            raise HTTPException(status_code=400, detail="No podes quitarte a vos mismo el rol admin.")

        if datos.email is not None:
            email_existente = db.execute(
                text("SELECT id FROM usuarios WHERE email = :email AND id <> :id"),
                {"email": str(datos.email).lower(), "id": usuario_id},
            ).fetchone()
            if email_existente:
                raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email.")

        campos_usuario: list[str] = []
        params_usuario: dict[str, object] = {"id": usuario_id}

        if datos.nombre is not None:
            campos_usuario.append("nombre = :nombre")
            params_usuario["nombre"] = datos.nombre
        if datos.apellido is not None:
            campos_usuario.append("apellido = :apellido")
            params_usuario["apellido"] = datos.apellido
        if datos.email is not None:
            campos_usuario.append("email = :email")
            params_usuario["email"] = str(datos.email).lower()
        if datos.telefono is not None:
            campos_usuario.append("telefono = :telefono")
            params_usuario["telefono"] = datos.telefono
        if datos.rol is not None:
            campos_usuario.append("rol = :rol")
            params_usuario["rol"] = nuevo_rol
        if datos.nueva_contrasenia is not None:
            campos_usuario.append("password_hash = :password_hash")
            params_usuario["password_hash"] = hashear_password(datos.nueva_contrasenia)
            campos_usuario.append("password_version = COALESCE(password_version, 1) + 1")

        if campos_usuario:
            db.execute(
                text(f"UPDATE usuarios SET {', '.join(campos_usuario)} WHERE id = :id"),
                params_usuario,
            )

        db.execute(
            text(
                """
                INSERT INTO personal_interno (usuario_id, area, cargo, responsabilidades)
                VALUES (:usuario_id, :area, :cargo, :responsabilidades)
                ON CONFLICT (usuario_id)
                DO UPDATE SET
                    area = COALESCE(:area, personal_interno.area),
                    cargo = COALESCE(:cargo, personal_interno.cargo),
                    responsabilidades = COALESCE(:responsabilidades, personal_interno.responsabilidades),
                    updated_at = NOW()
                """
            ),
            {
                "usuario_id": usuario_id,
                "area": datos.area,
                "cargo": datos.cargo,
                "responsabilidades": datos.responsabilidades,
            },
        )
        _sincronizar_empresas_visibles(
            db,
            usuario_id=usuario_id,
            rol=nuevo_rol,
            empresa_ids=datos.empresa_ids,
        )

        db.execute(
            text(
                """
                INSERT INTO auditoria (accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos)
                VALUES (:accion, 'usuarios', :registro_id, :datos_anteriores, :datos_nuevos)
                """
            ),
            {
                "accion": "actualizar_personal_interno",
                "registro_id": usuario_id,
                "datos_anteriores": json.dumps(
                    {
                        "rol": actual.rol,
                        "area": actual.area,
                        "cargo": actual.cargo,
                        "responsabilidades": actual.responsabilidades,
                    }
                ),
                "datos_nuevos": json.dumps(
                    {
                        "rol": nuevo_rol,
                        "area": datos.area if datos.area is not None else actual.area,
                        "cargo": datos.cargo if datos.cargo is not None else actual.cargo,
                        "responsabilidades": datos.responsabilidades if datos.responsabilidades is not None else actual.responsabilidades,
                        "empresa_ids": datos.empresa_ids if datos.empresa_ids is not None else actual.empresa_ids,
                        "actor_user_id": actor_user_id,
                    }
                ),
            },
        )

        db.commit()
        return _fetch_personal_item(db, usuario_id)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def _normalizar_rol(rol: str) -> str:
    clean = (rol or "").strip().lower()
    if clean not in PERSONAL_ROLES:
        raise HTTPException(status_code=400, detail="Rol interno no valido.")
    return clean


def _fetch_personal_row(db: Session, usuario_id: int):
    return db.execute(
        text(
            """
            SELECT
                u.id,
                u.nombre,
                u.apellido,
                u.email,
                u.telefono,
                u.rol,
                u.activo,
                u.created_at,
                p.area,
                p.cargo,
                p.responsabilidades,
                p.updated_at AS perfil_updated_at,
                COUNT(DISTINCT gep.empresa_id) AS empresas_visibles_count,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT e.razon_social), NULL) AS empresas_visibles,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT gep.empresa_id), NULL) AS empresa_ids
            FROM usuarios u
            LEFT JOIN personal_interno p ON p.usuario_id = u.id
            LEFT JOIN gestor_empresas_permitidas gep ON gep.usuario_id = u.id
            LEFT JOIN empresas e ON e.id = gep.empresa_id
            WHERE u.id = :id
              AND u.rol IN ('admin', 'gestor_interno')
            GROUP BY
                u.id,
                u.nombre,
                u.apellido,
                u.email,
                u.telefono,
                u.rol,
                u.activo,
                u.created_at,
                p.area,
                p.cargo,
                p.responsabilidades,
                p.updated_at
            """
        ),
        {"id": usuario_id},
    ).fetchone()


def _fetch_personal_item(db: Session, usuario_id: int):
    row = _fetch_personal_row(db, usuario_id)
    if not row:
        raise HTTPException(status_code=404, detail="Personal no encontrado.")
    return {
        "id": row.id,
        "nombre": row.nombre,
        "apellido": row.apellido,
        "email": row.email,
        "telefono": row.telefono,
        "rol": row.rol,
        "activo": row.activo,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "area": row.area,
        "cargo": row.cargo,
        "responsabilidades": row.responsabilidades,
        "perfil_updated_at": row.perfil_updated_at.isoformat() if row.perfil_updated_at else None,
        "empresas_visibles_count": row.empresas_visibles_count or 0,
        "empresas_visibles": list(row.empresas_visibles or []),
        "empresa_ids": [empresa_id for empresa_id in list(row.empresa_ids or []) if empresa_id is not None],
    }


def _sincronizar_empresas_visibles(
    db: Session,
    *,
    usuario_id: int,
    rol: str,
    empresa_ids: list[int] | None,
):
    if rol != "gestor_interno":
        db.execute(
            text("DELETE FROM gestor_empresas_permitidas WHERE usuario_id = :usuario_id"),
            {"usuario_id": usuario_id},
        )
        return

    if empresa_ids is None:
        return

    ids_unicos = sorted({empresa_id for empresa_id in empresa_ids if empresa_id > 0})
    if ids_unicos:
        existentes = db.execute(
            text("SELECT id FROM empresas WHERE id = ANY(:empresa_ids)"),
            {"empresa_ids": ids_unicos},
        ).fetchall()
        existentes_ids = {row.id for row in existentes}
        faltantes = [empresa_id for empresa_id in ids_unicos if empresa_id not in existentes_ids]
        if faltantes:
            raise HTTPException(status_code=400, detail="Hay empresas seleccionadas que no existen.")
    else:
        existentes_ids = set()

    db.execute(
        text("DELETE FROM gestor_empresas_permitidas WHERE usuario_id = :usuario_id"),
        {"usuario_id": usuario_id},
    )

    for empresa_id in sorted(existentes_ids):
        db.execute(
            text(
                """
                INSERT INTO gestor_empresas_permitidas (usuario_id, empresa_id)
                VALUES (:usuario_id, :empresa_id)
                """
            ),
            {"usuario_id": usuario_id, "empresa_id": empresa_id},
        )
