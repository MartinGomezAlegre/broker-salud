import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.empresas import CambiarEstadoEmpresa, EmpresaActualizar
from app.services.empresas.common import empresa_to_dict, registrar_auditoria

logger = logging.getLogger(__name__)


def actualizar_empresa(
    db: Session,
    empresa_id: int,
    datos: EmpresaActualizar,
):
    try:
        empresa = db.execute(
            text("SELECT id FROM empresas WHERE id = :id"),
            {"id": empresa_id},
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        campos = []
        params = {"id": empresa_id}
        for campo, valor in datos.model_dump(exclude_none=True).items():
            campos.append(f"{campo} = :{campo}")
            params[campo] = valor

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
