from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.empresas import EmpresaAcuerdoActualizar, EmpresaAcuerdoCrear
from app.services.empresas.common import serialize_value

logger = logging.getLogger(__name__)

TIPOS_ACUERDO = {"contrato", "acuerdo", "convenio", "nda", "otro"}
ESTADOS_ACUERDO = {"borrador", "vigente", "vencido", "rescindido"}


def listar_acuerdos_empresa(db: Session, empresa_id: int):
    try:
        _asegurar_empresa(db, empresa_id)
        rows = db.execute(
            text(
                """
                SELECT id, empresa_id, tipo, titulo, descripcion, estado,
                       fecha_firma, fecha_vencimiento, archivo_url, notas,
                       created_at, updated_at
                FROM empresa_acuerdos
                WHERE empresa_id = :empresa_id
                ORDER BY COALESCE(fecha_vencimiento, fecha_firma, created_at) DESC, id DESC
                """
            ),
            {"empresa_id": empresa_id},
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def crear_acuerdo_empresa(db: Session, empresa_id: int, datos: EmpresaAcuerdoCrear):
    try:
        _asegurar_empresa(db, empresa_id)
        payload = _normalizar_payload(datos.tipo, datos.estado)

        row = db.execute(
            text(
                """
                INSERT INTO empresa_acuerdos (
                    empresa_id, tipo, titulo, descripcion, estado,
                    fecha_firma, fecha_vencimiento, archivo_url, notas
                )
                VALUES (
                    :empresa_id, :tipo, :titulo, :descripcion, :estado,
                    :fecha_firma, :fecha_vencimiento, :archivo_url, :notas
                )
                RETURNING id, empresa_id, tipo, titulo, descripcion, estado,
                          fecha_firma, fecha_vencimiento, archivo_url, notas,
                          created_at, updated_at
                """
            ),
            {
                "empresa_id": empresa_id,
                "tipo": payload["tipo"],
                "titulo": datos.titulo.strip(),
                "descripcion": _normalizar_texto(datos.descripcion),
                "estado": payload["estado"],
                "fecha_firma": datos.fecha_firma,
                "fecha_vencimiento": datos.fecha_vencimiento,
                "archivo_url": _normalizar_texto(datos.archivo_url),
                "notas": _normalizar_texto(datos.notas),
            },
        ).fetchone()
        db.commit()
        return _row_to_dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_acuerdo_empresa(
    db: Session,
    empresa_id: int,
    acuerdo_id: int,
    datos: EmpresaAcuerdoActualizar,
):
    try:
        _obtener_acuerdo(db, empresa_id, acuerdo_id)

        campos: list[str] = []
        params: dict[str, object] = {"empresa_id": empresa_id, "acuerdo_id": acuerdo_id}

        if datos.tipo is not None:
            campos.append("tipo = :tipo")
            params["tipo"] = _normalizar_payload(datos.tipo, None)["tipo"]
        if datos.titulo is not None:
            campos.append("titulo = :titulo")
            params["titulo"] = datos.titulo.strip()
        if datos.descripcion is not None:
            campos.append("descripcion = :descripcion")
            params["descripcion"] = _normalizar_texto(datos.descripcion)
        if datos.estado is not None:
            campos.append("estado = :estado")
            params["estado"] = _normalizar_payload(None, datos.estado)["estado"]
        if datos.fecha_firma is not None:
            campos.append("fecha_firma = :fecha_firma")
            params["fecha_firma"] = datos.fecha_firma
        if datos.fecha_vencimiento is not None:
            campos.append("fecha_vencimiento = :fecha_vencimiento")
            params["fecha_vencimiento"] = datos.fecha_vencimiento
        if datos.archivo_url is not None:
            campos.append("archivo_url = :archivo_url")
            params["archivo_url"] = _normalizar_texto(datos.archivo_url)
        if datos.notas is not None:
            campos.append("notas = :notas")
            params["notas"] = _normalizar_texto(datos.notas)

        if not campos:
            raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar.")

        row = db.execute(
            text(
                f"""
                UPDATE empresa_acuerdos
                SET {', '.join(campos)}, updated_at = NOW()
                WHERE empresa_id = :empresa_id AND id = :acuerdo_id
                RETURNING id, empresa_id, tipo, titulo, descripcion, estado,
                          fecha_firma, fecha_vencimiento, archivo_url, notas,
                          created_at, updated_at
                """
            ),
            params,
        ).fetchone()
        db.commit()
        return _row_to_dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def eliminar_acuerdo_empresa(db: Session, empresa_id: int, acuerdo_id: int):
    try:
        acuerdo = _obtener_acuerdo(db, empresa_id, acuerdo_id)
        db.execute(
            text("DELETE FROM empresa_acuerdos WHERE empresa_id = :empresa_id AND id = :acuerdo_id"),
            {"empresa_id": empresa_id, "acuerdo_id": acuerdo_id},
        )
        db.commit()
        return {"ok": True, "id": acuerdo.id}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def _asegurar_empresa(db: Session, empresa_id: int):
    empresa = db.execute(
        text("SELECT id FROM empresas WHERE id = :empresa_id"),
        {"empresa_id": empresa_id},
    ).fetchone()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


def _obtener_acuerdo(db: Session, empresa_id: int, acuerdo_id: int):
    _asegurar_empresa(db, empresa_id)
    acuerdo = db.execute(
        text(
            """
            SELECT id, empresa_id, tipo, titulo, descripcion, estado,
                   fecha_firma, fecha_vencimiento, archivo_url, notas,
                   created_at, updated_at
            FROM empresa_acuerdos
            WHERE empresa_id = :empresa_id AND id = :acuerdo_id
            """
        ),
        {"empresa_id": empresa_id, "acuerdo_id": acuerdo_id},
    ).fetchone()
    if not acuerdo:
        raise HTTPException(status_code=404, detail="Acuerdo no encontrado")
    return acuerdo


def _normalizar_payload(tipo: str | None, estado: str | None):
    resultado: dict[str, str] = {}
    if tipo is not None:
        tipo_normalizado = tipo.strip().lower()
        if tipo_normalizado not in TIPOS_ACUERDO:
            raise HTTPException(status_code=400, detail="Tipo de acuerdo no valido.")
        resultado["tipo"] = tipo_normalizado
    if estado is not None:
        estado_normalizado = estado.strip().lower()
        if estado_normalizado not in ESTADOS_ACUERDO:
            raise HTTPException(status_code=400, detail="Estado de acuerdo no valido.")
        resultado["estado"] = estado_normalizado
    return resultado


def _normalizar_texto(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "empresa_id": row.empresa_id,
        "tipo": row.tipo,
        "titulo": row.titulo,
        "descripcion": row.descripcion,
        "estado": row.estado,
        "fecha_firma": serialize_value(row.fecha_firma),
        "fecha_vencimiento": serialize_value(row.fecha_vencimiento),
        "archivo_url": row.archivo_url,
        "notas": row.notas,
        "created_at": serialize_value(row.created_at),
        "updated_at": serialize_value(row.updated_at),
    }
