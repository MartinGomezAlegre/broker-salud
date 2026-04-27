from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.catalogo import (
    FarmaciaActualizar,
    FarmaciaCrear,
    MedicamentoActualizar,
    MedicamentoCrear,
)
from app.services.catalogo.common import logger, registrar_auditoria, row_to_dict


MEDICATION_FIELDS_SQL = """
    m.id,
    m.nombre,
    m.principio_activo,
    m.presentacion,
    m.laboratorio,
    m.descripcion,
    m.cobertura_resumen,
    m.descuento_porcentaje,
    m.keywords,
    m.activo,
    m.orden_display,
    m.created_at,
    m.updated_at
"""

PHARMACY_FIELDS_SQL = """
    f.id,
    f.nombre,
    f.direccion,
    f.localidad,
    f.provincia,
    f.telefono,
    f.horario,
    f.estado_atencion,
    f.distancia_km,
    f.descuento_porcentaje,
    f.maps_url,
    f.descripcion,
    f.activo,
    f.orden_display,
    f.created_at,
    f.updated_at
"""


def listar_medicamentos_admin(db: Session):
    try:
        rows = db.execute(
            text(
                f"""
                SELECT {MEDICATION_FIELDS_SQL}
                FROM vademecum_medicamentos m
                ORDER BY m.activo DESC, m.orden_display ASC NULLS LAST, m.nombre ASC
                """
            )
        ).fetchall()
        return [_serialize_medication(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al listar medicamentos admin: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def listar_medicamentos_cliente(
    db: Session,
    q: str | None = None,
    limit: int = 20,
):
    try:
        filters = ["m.activo = true"]
        params: dict[str, Any] = {"limit": limit}

        if q and q.strip():
            params["query"] = f"%{q.strip()}%"
            filters.append(
                """
                (
                    m.nombre ILIKE :query
                    OR COALESCE(m.principio_activo, '') ILIKE :query
                    OR COALESCE(m.laboratorio, '') ILIKE :query
                    OR COALESCE(m.presentacion, '') ILIKE :query
                    OR COALESCE(m.keywords, '') ILIKE :query
                )
                """
            )

        rows = db.execute(
            text(
                f"""
                SELECT {MEDICATION_FIELDS_SQL}
                FROM vademecum_medicamentos m
                WHERE {' AND '.join(filters)}
                ORDER BY m.orden_display ASC NULLS LAST, m.nombre ASC
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()
        return [_serialize_medication(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al listar medicamentos cliente: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def crear_medicamento(db: Session, datos: MedicamentoCrear):
    try:
        payload = datos.model_dump()
        row = db.execute(
            text(
                """
                INSERT INTO vademecum_medicamentos
                    (nombre, principio_activo, presentacion, laboratorio, descripcion,
                     cobertura_resumen, descuento_porcentaje, keywords, activo, orden_display)
                VALUES
                    (:nombre, :principio_activo, :presentacion, :laboratorio, :descripcion,
                     :cobertura_resumen, :descuento_porcentaje, :keywords, :activo, :orden_display)
                RETURNING id
                """
            ),
            payload,
        ).fetchone()
        created = _get_medicamento_by_id(db, row.id)
        registrar_auditoria(db, "crear_medicamento", "vademecum_medicamentos", row.id, {}, created)
        db.commit()
        return created
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al crear medicamento: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_medicamento(db: Session, medicamento_id: int, datos: MedicamentoActualizar):
    try:
        anterior = _get_medicamento_by_id(db, medicamento_id)
        cambios = {key: value for key, value in datos.model_dump(exclude_none=True).items()}
        if cambios:
            db.execute(
                text(
                    f"""
                    UPDATE vademecum_medicamentos
                    SET {', '.join(f'{campo} = :{campo}' for campo in cambios)}, updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": medicamento_id, **cambios},
            )
        actualizado = _get_medicamento_by_id(db, medicamento_id)
        accion = "cambiar_estado_medicamento" if set(cambios.keys()) == {"activo"} else "actualizar_medicamento"
        registrar_auditoria(db, accion, "vademecum_medicamentos", medicamento_id, anterior, actualizado)
        db.commit()
        return actualizado
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al actualizar medicamento: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def listar_farmacias_admin(db: Session):
    try:
        rows = db.execute(
            text(
                f"""
                SELECT {PHARMACY_FIELDS_SQL}
                FROM farmacias_adheridas f
                ORDER BY f.activo DESC, f.orden_display ASC NULLS LAST, f.nombre ASC
                """
            )
        ).fetchall()
        return [_serialize_pharmacy(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al listar farmacias admin: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def listar_farmacias_cliente(
    db: Session,
    q: str | None = None,
    localidad: str | None = None,
    limit: int = 20,
):
    try:
        filters = ["f.activo = true"]
        params: dict[str, Any] = {"limit": limit}

        if q and q.strip():
            params["query"] = f"%{q.strip()}%"
            filters.append(
                """
                (
                    f.nombre ILIKE :query
                    OR f.direccion ILIKE :query
                    OR COALESCE(f.localidad, '') ILIKE :query
                    OR COALESCE(f.descripcion, '') ILIKE :query
                )
                """
            )

        if localidad and localidad.strip():
            params["localidad"] = f"%{localidad.strip()}%"
            filters.append("COALESCE(f.localidad, '') ILIKE :localidad")

        rows = db.execute(
            text(
                f"""
                SELECT {PHARMACY_FIELDS_SQL}
                FROM farmacias_adheridas f
                WHERE {' AND '.join(filters)}
                ORDER BY f.orden_display ASC NULLS LAST, f.distancia_km ASC NULLS LAST, f.nombre ASC
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()
        return [_serialize_pharmacy(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al listar farmacias cliente: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def crear_farmacia(db: Session, datos: FarmaciaCrear):
    try:
        payload = datos.model_dump()
        row = db.execute(
            text(
                """
                INSERT INTO farmacias_adheridas
                    (nombre, direccion, localidad, provincia, telefono, horario, estado_atencion,
                     distancia_km, descuento_porcentaje, maps_url, descripcion, activo, orden_display)
                VALUES
                    (:nombre, :direccion, :localidad, :provincia, :telefono, :horario, :estado_atencion,
                     :distancia_km, :descuento_porcentaje, :maps_url, :descripcion, :activo, :orden_display)
                RETURNING id
                """
            ),
            payload,
        ).fetchone()
        created = _get_farmacia_by_id(db, row.id)
        registrar_auditoria(db, "crear_farmacia", "farmacias_adheridas", row.id, {}, created)
        db.commit()
        return created
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al crear farmacia: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_farmacia(db: Session, farmacia_id: int, datos: FarmaciaActualizar):
    try:
        anterior = _get_farmacia_by_id(db, farmacia_id)
        cambios = {key: value for key, value in datos.model_dump(exclude_none=True).items()}
        if cambios:
            db.execute(
                text(
                    f"""
                    UPDATE farmacias_adheridas
                    SET {', '.join(f'{campo} = :{campo}' for campo in cambios)}, updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": farmacia_id, **cambios},
            )
        actualizado = _get_farmacia_by_id(db, farmacia_id)
        accion = "cambiar_estado_farmacia" if set(cambios.keys()) == {"activo"} else "actualizar_farmacia"
        registrar_auditoria(db, accion, "farmacias_adheridas", farmacia_id, anterior, actualizado)
        db.commit()
        return actualizado
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al actualizar farmacia: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def _get_medicamento_by_id(db: Session, medicamento_id: int):
    row = db.execute(
        text(
            f"""
            SELECT {MEDICATION_FIELDS_SQL}
            FROM vademecum_medicamentos m
            WHERE m.id = :id
            """
        ),
        {"id": medicamento_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado.")
    return _serialize_medication(row)


def _get_farmacia_by_id(db: Session, farmacia_id: int):
    row = db.execute(
        text(
            f"""
            SELECT {PHARMACY_FIELDS_SQL}
            FROM farmacias_adheridas f
            WHERE f.id = :id
            """
        ),
        {"id": farmacia_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Farmacia no encontrada.")
    return _serialize_pharmacy(row)


def _serialize_medication(row) -> dict[str, Any]:
    payload = row_to_dict(row)
    return payload


def _serialize_pharmacy(row) -> dict[str, Any]:
    payload = row_to_dict(row)
    if isinstance(payload.get("distancia_km"), Decimal):
        payload["distancia_km"] = float(payload["distancia_km"])
    return payload
