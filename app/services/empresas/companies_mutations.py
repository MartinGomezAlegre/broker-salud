import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.empresas import CambiarEstadoEmpresa, EmpresaActualizar
from app.services.comercial.accounts import create_commercial_user, update_commercial_user
from app.services.empresas.common import empresa_to_dict, registrar_auditoria

logger = logging.getLogger(__name__)


def actualizar_empresa(
    db: Session,
    empresa_id: int,
    datos: EmpresaActualizar,
):
    try:
        empresa = db.execute(
            text(
                """
                SELECT e.id, e.contacto_nombre, e.admin_user_id, admin_u.email AS admin_access_email
                FROM empresas e
                LEFT JOIN usuarios admin_u ON admin_u.id = e.admin_user_id
                WHERE e.id = :id
                """
            ),
            {"id": empresa_id},
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        admin_access_email = _clean_optional(datos.admin_access_email)
        admin_access_password = _clean_optional(datos.admin_access_password)

        campos = []
        params = {"id": empresa_id}
        payload = datos.model_dump(exclude_none=True)
        payload.pop("admin_access_email", None)
        payload.pop("admin_access_password", None)

        for campo, valor in payload.items():
            campos.append(f"{campo} = :{campo}")
            params[campo] = valor

        next_contact_name = payload.get("contacto_nombre") or empresa.contacto_nombre or "Empresa admin"
        if empresa.admin_user_id:
            if admin_access_email or admin_access_password or "contacto_nombre" in payload:
                resolved_email = admin_access_email or empresa.admin_access_email
                if not resolved_email:
                    raise HTTPException(
                        status_code=400,
                        detail="La empresa ya tiene un usuario administrador, pero falta su email de acceso.",
                    )
                update_commercial_user(
                    db,
                    usuario_id=empresa.admin_user_id,
                    full_name=next_contact_name,
                    email=resolved_email,
                    role="empresa_admin",
                    password=admin_access_password,
                )
        elif admin_access_email or admin_access_password:
            if not admin_access_email or not admin_access_password:
                raise HTTPException(
                    status_code=400,
                    detail="Para crear el acceso empresa_admin necesitas email y contrasena inicial.",
                )
            params["admin_user_id"] = create_commercial_user(
                db,
                full_name=next_contact_name,
                email=admin_access_email,
                password=admin_access_password,
                role="empresa_admin",
            )
            campos.append("admin_user_id = :admin_user_id")

        if campos:
            db.execute(
                text(f"UPDATE empresas SET {', '.join(campos)} WHERE id = :id"),
                params,
            )
            db.commit()

        actualizada = db.execute(
            text("SELECT * FROM empresas WHERE id = :id"),
            {"id": empresa_id},
        ).fetchone()
        return empresa_to_dict(actualizada)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def cambiar_estado_empresa(
    db: Session,
    empresa_id: int,
    datos: CambiarEstadoEmpresa,
):
    try:
        empresa = db.execute(
            text("SELECT id, razon_social, activo FROM empresas WHERE id = :id"),
            {"id": empresa_id},
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        db.execute(
            text("UPDATE empresas SET activo = :activo WHERE id = :id"),
            {"activo": datos.activo, "id": empresa_id},
        )

        if not datos.activo:
            db.execute(
                text("UPDATE empleados_empresa SET activo = false WHERE empresa_id = :id"),
                {"id": empresa_id},
            )
            db.execute(text("""
                UPDATE suscripciones_empresariales
                SET estado = 'cancelada'
                WHERE empresa_id = :id AND estado NOT IN ('cancelada', 'vencida')
            """), {"id": empresa_id})
        else:
            db.execute(text("""
                UPDATE suscripciones_empresariales
                SET estado = 'pendiente_pago'
                WHERE empresa_id = :id AND estado = 'cancelada'
            """), {"id": empresa_id})

        accion = "dar_de_alta_empresa" if datos.activo else "dar_de_baja_empresa"
        registrar_auditoria(
            db,
            accion,
            "empresas",
            empresa_id,
            {"activo": empresa.activo},
            {"activo": datos.activo, "motivo": datos.motivo},
        )
        db.commit()

        actualizada = db.execute(
            text("SELECT * FROM empresas WHERE id = :id"),
            {"id": empresa_id},
        ).fetchone()
        return empresa_to_dict(actualizada)
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
