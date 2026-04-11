from datetime import date, timedelta
import json

from sqlalchemy import text
from sqlalchemy.orm import Session


def serialize_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def empresa_to_dict(row) -> dict:
    data = {
        key: serialize_value(value)
        for key, value in row._mapping.items()
    }
    if "email_contacto" in data:
        data["contacto_email"] = data.pop("email_contacto")
    return data


def empleado_to_dict(row) -> dict:
    return {
        "id": row.id,
        "nombre": row.nombre,
        "apellido": row.apellido,
        "dni": row.dni,
        "email": row.email,
        "cargo": row.cargo,
        "telefono": row.telefono,
        "activo": row.activo,
        "fecha_alta": serialize_value(row.fecha_alta),
        "fecha_baja": serialize_value(row.fecha_baja),
        "usuario_id": row.usuario_id,
    }


def calcular_fecha_fin(fecha_inicio: date, periodicidad: str) -> date:
    dias = {"mensual": 30, "trimestral": 90, "anual": 365}
    return fecha_inicio + timedelta(days=dias.get(periodicidad, 30))


def registrar_auditoria(
    db: Session,
    accion: str,
    tabla: str,
    registro_id: int,
    datos_anteriores: dict,
    datos_nuevos: dict,
):
    db.execute(text("""
        INSERT INTO auditoria (accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos)
        VALUES (:accion, :tabla, :registro_id, :datos_anteriores, :datos_nuevos)
    """), {
        "accion": accion,
        "tabla": tabla,
        "registro_id": registro_id,
        "datos_anteriores": json.dumps(datos_anteriores),
        "datos_nuevos": json.dumps(datos_nuevos),
    })
