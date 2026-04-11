from datetime import date
import logging
from typing import List

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.empresas import BulkEmpleados, CambiarEstadoEmpleado, EmpleadoActualizar, EmpleadoCrear
from app.services.empresas.common import empleado_to_dict, registrar_auditoria

logger = logging.getLogger(__name__)


def agregar_empleado(
    db: Session,
    empresa_id: int,
    datos: EmpleadoCrear,
):
    try:
        _assert_empresa_exists(db, empresa_id)
        empleado = _crear_empleado(db, empresa_id, datos)
        db.commit()
        return empleado
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def agregar_empleados_bulk(
    db: Session,
    empresa_id: int,
    datos: BulkEmpleados,
):
    try:
        _assert_empresa_exists(db, empresa_id)

        empleados_lista: List[EmpleadoCrear] = _parse_bulk_empleados(datos)
        if len(empleados_lista) > 500:
            raise HTTPException(status_code=400, detail="Maximo 500 empleados por request")

        cargados = 0
        errores = []
        for empleado in empleados_lista:
            try:
                _crear_empleado(db, empresa_id, empleado)
                cargados += 1
            except HTTPException as exc:
                errores.append(f"{empleado.email}: {exc.detail}")
            except Exception as exc:
                errores.append(f"{empleado.email}: {str(exc)}")

        db.commit()
        return {"cargados": cargados, "fallidos": len(errores), "errores": errores}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_empleado(
    db: Session,
    empresa_id: int,
    empleado_id: int,
    datos: EmpleadoActualizar,
):
    try:
        empleado = db.execute(text("""
            SELECT id FROM empleados_empresa
            WHERE id = :id AND empresa_id = :empresa_id
        """), {"id": empleado_id, "empresa_id": empresa_id}).fetchone()
        if not empleado:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        campos = []
        params = {"id": empleado_id}
        for campo, valor in datos.model_dump(exclude_none=True).items():
            campos.append(f"{campo} = :{campo}")
            params[campo] = valor

        if campos:
            db.execute(
                text(f"UPDATE empleados_empresa SET {', '.join(campos)} WHERE id = :id"),
                params,
            )
            db.commit()

        actualizado = db.execute(text("""
            SELECT id, nombre, apellido, dni, email, cargo, telefono,
                   activo, fecha_alta, fecha_baja, usuario_id
            FROM empleados_empresa WHERE id = :id
        """), {"id": empleado_id}).fetchone()

        return empleado_to_dict(actualizado)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def cambiar_estado_empleado(
    db: Session,
    empresa_id: int,
    empleado_id: int,
    datos: CambiarEstadoEmpleado,
):
    try:
        empleado = db.execute(text("""
            SELECT id, activo FROM empleados_empresa
            WHERE id = :id AND empresa_id = :empresa_id
        """), {"id": empleado_id, "empresa_id": empresa_id}).fetchone()
        if not empleado:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        if datos.activo:
            db.execute(text("""
                UPDATE empleados_empresa SET activo = true, fecha_baja = null
                WHERE id = :id
            """), {"id": empleado_id})
        else:
            db.execute(text("""
                UPDATE empleados_empresa SET activo = false, fecha_baja = CURRENT_DATE
                WHERE id = :id
            """), {"id": empleado_id})

        registrar_auditoria(
            db,
            "cambiar_estado_empleado",
            "empleados_empresa",
            empleado_id,
            {"activo": empleado.activo},
            {"activo": datos.activo, "motivo": datos.motivo},
        )
        db.commit()

        actualizado = db.execute(text("""
            SELECT id, nombre, apellido, dni, email, cargo, telefono,
                   activo, fecha_alta, fecha_baja, usuario_id
            FROM empleados_empresa WHERE id = :id
        """), {"id": empleado_id}).fetchone()
        return empleado_to_dict(actualizado)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def eliminar_empleado(
    db: Session,
    empresa_id: int,
    empleado_id: int,
):
    try:
        empleado = db.execute(text("""
            SELECT id, activo, fecha_alta FROM empleados_empresa
            WHERE id = :id AND empresa_id = :empresa_id
        """), {"id": empleado_id, "empresa_id": empresa_id}).fetchone()
        if not empleado:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        if empleado.fecha_alta != date.today():
            raise HTTPException(status_code=400, detail="No se puede eliminar: usar dar de baja en su lugar")

        db.execute(
            text("DELETE FROM empleados_empresa WHERE id = :id"),
            {"id": empleado_id},
        )
        db.commit()
        return {"mensaje": "Empleado eliminado correctamente"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def _assert_empresa_exists(db: Session, empresa_id: int) -> None:
    empresa = db.execute(
        text("SELECT id FROM empresas WHERE id = :id"),
        {"id": empresa_id},
    ).fetchone()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")


def _crear_empleado(
    db: Session,
    empresa_id: int,
    datos: EmpleadoCrear,
) -> dict:
    existente = db.execute(text("""
        SELECT id FROM empleados_empresa
        WHERE empresa_id = :empresa_id AND email = :email
    """), {"empresa_id": empresa_id, "email": datos.email}).fetchone()
    if existente:
        raise HTTPException(status_code=400, detail=f"El email {datos.email} ya esta registrado en esta empresa")

    usuario = db.execute(
        text("SELECT id FROM usuarios WHERE email = :email"),
        {"email": datos.email},
    ).fetchone()
    usuario_id = usuario.id if usuario else None

    result = db.execute(text("""
        INSERT INTO empleados_empresa
          (empresa_id, nombre, apellido, dni, email, cargo, telefono, activo, fecha_alta, usuario_id)
        VALUES
          (:empresa_id, :nombre, :apellido, :dni, :email, :cargo, :telefono, true, CURRENT_DATE, :usuario_id)
        RETURNING id, nombre, apellido, dni, email, cargo, telefono, activo, fecha_alta, fecha_baja, usuario_id
    """), {
        "empresa_id": empresa_id,
        "nombre": datos.nombre,
        "apellido": datos.apellido,
        "dni": datos.dni,
        "email": datos.email,
        "cargo": datos.cargo,
        "telefono": datos.telefono,
        "usuario_id": usuario_id,
    }).fetchone()

    return empleado_to_dict(result)


def _parse_bulk_empleados(datos: BulkEmpleados) -> List[EmpleadoCrear]:
    if datos.datos:
        empleados_lista: List[EmpleadoCrear] = []
        for linea in datos.datos.strip().splitlines():
            linea = linea.strip()
            if not linea:
                continue
            partes = [parte.strip() for parte in linea.split(",")]
            if len(partes) < 4:
                continue
            empleados_lista.append(EmpleadoCrear(
                nombre=partes[0],
                apellido=partes[1],
                dni=partes[2],
                email=partes[3],
                cargo=partes[4] if len(partes) > 4 else None,
                telefono=partes[5] if len(partes) > 5 else None,
            ))
        return empleados_lista

    if datos.empleados:
        return datos.empleados

    raise HTTPException(status_code=400, detail="Debe enviar 'datos' (CSV) o 'empleados' (JSON)")
