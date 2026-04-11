import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.empresas.common import empleado_to_dict

logger = logging.getLogger(__name__)


def listar_empleados(
    db: Session,
    empresa_id: int,
    activo: bool | None,
):
    try:
        filtro = "AND em.activo = :activo" if activo is not None else ""
        params = {"empresa_id": empresa_id}
        if activo is not None:
            params["activo"] = activo

        rows = db.execute(text(f"""
            SELECT id, nombre, apellido, dni, email, cargo, telefono,
                   activo, fecha_alta, fecha_baja, usuario_id
            FROM empleados_empresa em
            WHERE empresa_id = :empresa_id {filtro}
            ORDER BY fecha_alta DESC
        """), params).fetchall()

        return [empleado_to_dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
