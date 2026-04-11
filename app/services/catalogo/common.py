import json
import logging
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def serialize_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize_mapping(data: dict | None) -> dict:
    return {
        key: serialize_value(value)
        for key, value in (data or {}).items()
    }


def row_to_dict(row) -> dict:
    return normalize_mapping(dict(row._mapping.items()))


def registrar_auditoria(
    db: Session,
    accion: str,
    tabla: str,
    registro_id: int,
    datos_anteriores: dict | None,
    datos_nuevos: dict | None,
):
    db.execute(text("""
        INSERT INTO auditoria (accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos)
        VALUES (:accion, :tabla, :registro_id, :datos_anteriores, :datos_nuevos)
    """), {
        "accion": accion,
        "tabla": tabla,
        "registro_id": registro_id,
        "datos_anteriores": json.dumps(normalize_mapping(datos_anteriores)),
        "datos_nuevos": json.dumps(normalize_mapping(datos_nuevos)),
    })


def descripcion_historial(
    accion: str,
    registro_id: int,
    anteriores: dict,
    nuevos: dict,
) -> str:
    if accion == "cambio_precio_plan":
        anterior = anteriores.get("precio_mensual")
        nuevo = nuevos.get("precio_mensual")
        if anterior is not None and nuevo is not None:
            return f"Precio del plan actualizado de ARS {anterior} a ARS {nuevo}"
        return "Precio del plan actualizado"

    nombre_plan = nuevos.get("nombre") or anteriores.get("nombre") or f"#{registro_id}"
    if accion == "crear_plan":
        return f"Se creo el plan {nombre_plan}"
    if accion == "actualizar_plan":
        return f"Se actualizaron los datos del plan {nombre_plan}"
    if accion == "cambiar_estado_plan":
        estado = "activo" if nuevos.get("activo") else "inactivo"
        return f"El plan {nombre_plan} paso a estado {estado}"

    codigo = nuevos.get("codigo") or anteriores.get("codigo") or f"#{registro_id}"
    if accion == "crear_cupon":
        return f"Se emitio el cupon {codigo}"
    if accion == "actualizar_cupon":
        return f"Se editaron los datos del cupon {codigo}"
    if accion == "cambiar_estado_cupon":
        estado = "activo" if nuevos.get("activo") else "inactivo"
        return f"El cupon {codigo} paso a estado {estado}"
    if accion == "desactivar_cupon_por_usos":
        return f"El cupon {codigo} se desactivo por tener usos registrados"
    if accion == "eliminar_cupon":
        return f"Se elimino el cupon {codigo}"

    return accion.replace("_", " ").capitalize()
