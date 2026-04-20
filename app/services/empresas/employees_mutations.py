from datetime import date
import io
import logging
import re
import unicodedata
from typing import Any, List

import openpyxl
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.empresas import BulkEmpleados, CambiarEstadoEmpleado, EmpleadoActualizar, EmpleadoCrear
from app.security.validators import normalize_dni, normalize_phone
from app.services.empresas.common import empleado_to_dict, registrar_auditoria

logger = logging.getLogger(__name__)

REQUIRED_BULK_HEADERS = {"nombre", "apellido", "dni", "email"}
OPTIONAL_BULK_HEADERS = {"cargo", "telefono"}
ALL_BULK_HEADERS = REQUIRED_BULK_HEADERS | OPTIONAL_BULK_HEADERS
MAX_BULK_EMPLOYEES = 500
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


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
        if len(empleados_lista) > MAX_BULK_EMPLOYEES:
            raise HTTPException(status_code=400, detail=f"Maximo {MAX_BULK_EMPLOYEES} empleados por request")

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


def analizar_empleados_bulk_xlsx(
    db: Session,
    empresa_id: int,
    file_bytes: bytes,
) -> dict[str, Any]:
    try:
        _assert_empresa_exists(db, empresa_id)
        analysis = _parse_empleados_workbook(file_bytes)
        return {
            "total_filas": analysis["total_rows"],
            "validas": len(analysis["parsed_rows"]),
            "invalidas": len(analysis["errores"]),
            "preview": analysis["preview"],
            "errores": analysis["errores"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def agregar_empleados_bulk_xlsx(
    db: Session,
    empresa_id: int,
    file_bytes: bytes,
) -> dict[str, Any]:
    try:
        _assert_empresa_exists(db, empresa_id)
        analysis = _parse_empleados_workbook(file_bytes)

        cargados = 0
        errores = list(analysis["errores"])
        for item in analysis["parsed_rows"]:
            empleado = item["empleado"]
            fila = item["fila"]
            try:
                _crear_empleado(db, empresa_id, empleado)
                cargados += 1
            except HTTPException as exc:
                errores.append({"fila": fila, "campo": "email", "mensaje": str(exc.detail)})
            except Exception as exc:
                errores.append({"fila": fila, "campo": None, "mensaje": str(exc)})

        db.commit()
        return {
            "cargados": cargados,
            "fallidos": len(errores),
            "errores": errores,
            "preview": analysis["preview"],
        }
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


def _parse_empleados_workbook(file_bytes: bytes) -> dict[str, Any]:
    try:
        workbook = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="No pudimos leer el archivo XLSX. Verifica el formato.") from exc

    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="El archivo esta vacio")

    header_map = _build_header_map(rows[0])
    missing_headers = [header for header in REQUIRED_BULK_HEADERS if header not in header_map]
    if missing_headers:
        faltantes = ", ".join(_display_header_name(header) for header in missing_headers)
        raise HTTPException(status_code=400, detail=f"Faltan columnas obligatorias en la plantilla: {faltantes}")

    parsed_rows: list[dict[str, Any]] = []
    preview: list[dict[str, Any]] = []
    errores: list[dict[str, Any]] = []
    seen_emails: set[str] = set()
    total_rows = 0

    for fila_numero, row in enumerate(rows[1:], start=2):
        raw_data = _extract_row_data(row, header_map)
        if _row_is_empty(raw_data):
            continue

        total_rows += 1
        if total_rows > MAX_BULK_EMPLOYEES:
            raise HTTPException(status_code=400, detail=f"Maximo {MAX_BULK_EMPLOYEES} empleados por archivo")

        row_errors = _validate_row_data(raw_data, fila_numero, seen_emails)
        if row_errors:
            errores.extend(row_errors)
            continue

        try:
            empleado = EmpleadoCrear(**raw_data)
        except ValidationError as exc:
            for issue in exc.errors():
                campo = issue["loc"][0] if issue.get("loc") else None
                errores.append({
                    "fila": fila_numero,
                    "campo": str(campo) if campo else None,
                    "mensaje": issue.get("msg", "Fila invalida"),
                })
            continue

        parsed_rows.append({"fila": fila_numero, "empleado": empleado})
        if len(preview) < 20:
            preview.append({"fila": fila_numero, **raw_data})

    return {
        "parsed_rows": parsed_rows,
        "preview": preview,
        "errores": errores,
        "total_rows": total_rows,
    }


def _build_header_map(header_row: tuple[Any, ...]) -> dict[str, int]:
    header_map: dict[str, int] = {}
    for index, cell in enumerate(header_row):
        normalized = _normalize_header_name(cell)
        if normalized in ALL_BULK_HEADERS:
            header_map[normalized] = index
    return header_map


def _extract_row_data(row: tuple[Any, ...], header_map: dict[str, int]) -> dict[str, str | None]:
    data: dict[str, str | None] = {}
    for header in ALL_BULK_HEADERS:
        position = header_map.get(header)
        value = row[position] if position is not None and position < len(row) else None
        data[header] = _cell_to_string(value)
    return data


def _row_is_empty(data: dict[str, str | None]) -> bool:
    return all(not value for value in data.values())


def _validate_row_data(
    data: dict[str, str | None],
    fila_numero: int,
    seen_emails: set[str],
) -> list[dict[str, Any]]:
    errores: list[dict[str, Any]] = []

    for campo in REQUIRED_BULK_HEADERS:
        if not data.get(campo):
            errores.append({
                "fila": fila_numero,
                "campo": campo,
                "mensaje": f"El campo {_display_header_name(campo)} es obligatorio",
            })

    email = (data.get("email") or "").lower()
    if email and not EMAIL_PATTERN.fullmatch(email):
        errores.append({"fila": fila_numero, "campo": "email", "mensaje": "Ingresa un email valido"})
    if email and email in seen_emails:
        errores.append({"fila": fila_numero, "campo": "email", "mensaje": "El email esta repetido dentro del archivo"})
    elif email:
        seen_emails.add(email)
        data["email"] = email

    if data.get("dni"):
        try:
            data["dni"] = normalize_dni(data["dni"])
        except ValueError as exc:
            errores.append({"fila": fila_numero, "campo": "dni", "mensaje": str(exc)})

    if data.get("telefono"):
        try:
            data["telefono"] = normalize_phone(data["telefono"])
        except ValueError as exc:
            errores.append({"fila": fila_numero, "campo": "telefono", "mensaje": str(exc)})

    return errores


def _normalize_header_name(value: Any) -> str:
    text = _cell_to_string(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.lower().replace(" ", "_")


def _display_header_name(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _cell_to_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        clean = value.strip()
        return clean or None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() or None
