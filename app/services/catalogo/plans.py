from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.catalogo import PlanActualizar, PlanCrear, PlanOrden
from app.services.catalogo.common import logger, normalize_mapping, registrar_auditoria, row_to_dict


def listar_planes_admin(db: Session):
    try:
        rows = db.execute(text("""
            SELECT p.id, p.nombre, p.descripcion, p.tipo, p.precio_mensual,
                   p.precio_anual, p.max_beneficiarios, p.activo, p.badge,
                   p.orden_display, p.created_at,
                   COUNT(s.id) FILTER (WHERE s.estado = 'activa') AS suscriptores_activos
            FROM planes p
            LEFT JOIN suscripciones s ON s.plan_id = p.id
            GROUP BY p.id
            ORDER BY p.orden_display ASC NULLS LAST, p.created_at DESC
        """)).fetchall()

        return [
            {
                "id": row.id,
                "nombre": row.nombre,
                "descripcion": row.descripcion,
                "tipo": row.tipo,
                "precio_mensual": float(row.precio_mensual) if row.precio_mensual is not None else None,
                "precio_anual": float(row.precio_anual) if row.precio_anual is not None else None,
                "max_beneficiarios": row.max_beneficiarios,
                "activo": row.activo,
                "badge": row.badge,
                "orden_display": row.orden_display,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "suscriptores_activos": row.suscriptores_activos or 0,
                "suscriptores": row.suscriptores_activos or 0,
                "revenue_mensual": round((row.suscriptores_activos or 0) * float(row.precio_mensual or 0), 2),
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def crear_plan(
    db: Session,
    datos: PlanCrear,
):
    try:
        result = db.execute(text("""
            INSERT INTO planes
              (nombre, descripcion, tipo, precio_mensual, precio_anual,
               max_beneficiarios, badge, orden_display, activo)
            VALUES
              (:nombre, :descripcion, :tipo, :precio_mensual, :precio_anual,
               :max_beneficiarios, :badge, :orden_display, true)
            RETURNING id
        """), datos.model_dump()).fetchone()

        plan = db.execute(
            text("SELECT * FROM planes WHERE id = :id"),
            {"id": result.id},
        ).fetchone()
        registrar_auditoria(db, "crear_plan", "planes", result.id, {}, row_to_dict(plan))
        db.commit()

        return row_to_dict(plan)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_plan_catalogo(
    db: Session,
    plan_id: int,
    datos: PlanActualizar,
):
    try:
        plan = db.execute(
            text("SELECT * FROM planes WHERE id = :id"),
            {"id": plan_id},
        ).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        cambios = normalize_mapping(datos.model_dump(exclude_none=True))
        if not cambios:
            return row_to_dict(plan)

        update_fields = [f"{campo} = :{campo}" for campo in cambios]
        db.execute(
            text(f"UPDATE planes SET {', '.join(update_fields)} WHERE id = :id"),
            {"id": plan_id, **cambios},
        )

        actualizado = db.execute(
            text("SELECT * FROM planes WHERE id = :id"),
            {"id": plan_id},
        ).fetchone()

        payload_anterior = row_to_dict(plan)
        payload_actualizado = row_to_dict(actualizado)
        _registrar_auditoria_plan(db, plan_id, payload_anterior, payload_actualizado, cambios)
        db.commit()

        return payload_actualizado
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_orden_plan(
    db: Session,
    plan_id: int,
    datos: PlanOrden,
):
    try:
        plan = db.execute(
            text("SELECT id FROM planes WHERE id = :id"),
            {"id": plan_id},
        ).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        db.execute(
            text("UPDATE planes SET orden_display = :orden_display WHERE id = :id"),
            {"orden_display": datos.orden_display, "id": plan_id},
        )
        db.commit()

        return {
            "id": plan_id,
            "orden_display": datos.orden_display,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def _registrar_auditoria_plan(
    db: Session,
    plan_id: int,
    anterior: dict[str, Any],
    actualizado: dict[str, Any],
    cambios: dict[str, Any],
):
    if "precio_mensual" in cambios and anterior.get("precio_mensual") != actualizado.get("precio_mensual"):
        registrar_auditoria(
            db,
            "cambio_precio_plan",
            "planes",
            plan_id,
            {"precio_mensual": anterior.get("precio_mensual")},
            {"precio_mensual": actualizado.get("precio_mensual")},
        )

    cambios_restantes = {
        key: value
        for key, value in cambios.items()
        if key != "precio_mensual"
    }
    if cambios_restantes == {"activo": actualizado.get("activo")}:
        registrar_auditoria(
            db,
            "cambiar_estado_plan",
            "planes",
            plan_id,
            {"nombre": anterior.get("nombre"), "activo": anterior.get("activo")},
            {"nombre": actualizado.get("nombre"), "activo": actualizado.get("activo")},
        )
        return

    if cambios_restantes:
        registrar_auditoria(
            db,
            "actualizar_plan",
            "planes",
            plan_id,
            anterior,
            actualizado,
        )
