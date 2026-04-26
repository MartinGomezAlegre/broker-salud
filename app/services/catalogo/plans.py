from collections import defaultdict
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.catalogo import PlanActualizar, PlanCrear, PlanOrden
from app.services.catalogo.common import logger, normalize_mapping, registrar_auditoria, row_to_dict


SERVICE_FIELDS_SQL = """
    s.id,
    s.code,
    s.nombre,
    s.descripcion,
    s.proveedor,
    s.access_mode,
    s.access_instructions,
    s.cta_label,
    s.cta_url,
    s.activo,
    s.orden_display,
    s.created_at,
    s.updated_at
"""


def listar_servicios_catalogo(db: Session):
    try:
        rows = db.execute(
            text(
                f"""
                SELECT {SERVICE_FIELDS_SQL}
                FROM services s
                ORDER BY s.orden_display ASC NULLS LAST, s.nombre ASC
                """
            )
        ).fetchall()
        return [row_to_dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error al listar servicios: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def listar_planes_admin(db: Session):
    try:
        rows = db.execute(
            text(
                """
                SELECT p.id, p.nombre, p.descripcion, p.tipo, p.precio_mensual,
                       p.precio_anual, p.max_beneficiarios, p.activo, p.badge,
                       p.orden_display, p.created_at,
                       COUNT(s.id) FILTER (WHERE s.estado = 'activa') AS suscriptores_activos
                FROM planes p
                LEFT JOIN suscripciones s ON s.plan_id = p.id
                GROUP BY p.id
                ORDER BY p.orden_display ASC NULLS LAST, p.created_at DESC
                """
            )
        ).fetchall()

        plan_payloads = []
        plan_ids: list[int] = []
        for row in rows:
            plan_ids.append(row.id)
            plan_payloads.append(
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
            )

        return _attach_services_to_plans(db, plan_payloads, plan_ids)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def listar_planes_publicos(db: Session, tipo: str | None = None):
    try:
        filters = ["p.activo = true"]
        params: dict[str, Any] = {}

        if tipo == "personal":
            filters.append(
                """
                (
                    lower(COALESCE(p.tipo, '')) IN ('personal', 'familiar', 'b2c')
                    OR lower(COALESCE(p.tipo, '')) LIKE 'b2c%'
                )
                """
            )
        elif tipo == "empresa":
            filters.append(
                """
                (
                    lower(COALESCE(p.tipo, '')) IN ('empresa', 'corporativo', 'b2b', 'convenio')
                    OR lower(COALESCE(p.tipo, '')) LIKE 'b2b%'
                )
                """
            )

        rows = db.execute(
            text(
                f"""
                SELECT p.id, p.nombre, p.descripcion, p.precio_mensual, p.max_beneficiarios,
                       p.activo, p.tipo, p.badge, p.precio_anual, p.orden_display
                FROM planes p
                WHERE {' AND '.join(filters)}
                ORDER BY p.orden_display ASC NULLS LAST, p.precio_mensual ASC, p.id ASC
                """
            ),
            params,
        ).fetchall()

        plan_payloads = [row_to_dict(row) for row in rows]
        return _attach_services_to_plans(db, plan_payloads, [row.id for row in rows])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno al listar planes publicos: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def obtener_servicios_por_plan(db: Session, plan_id: int) -> list[dict[str, Any]]:
    plan_services = _attach_services_to_plans(db, [{"id": plan_id}], [plan_id])
    return plan_services[0].get("services", [])


def crear_plan(
    db: Session,
    datos: PlanCrear,
):
    try:
        service_ids = _validate_service_ids(db, datos.service_ids)

        payload = datos.model_dump(exclude={"service_ids"})
        result = db.execute(
            text(
                """
                INSERT INTO planes
                  (nombre, descripcion, tipo, precio_mensual, precio_anual,
                   max_beneficiarios, badge, orden_display, activo)
                VALUES
                  (:nombre, :descripcion, :tipo, :precio_mensual, :precio_anual,
                   :max_beneficiarios, :badge, :orden_display, :activo)
                RETURNING id
                """
            ),
            payload,
        ).fetchone()

        _replace_plan_services(db, result.id, service_ids)

        plan = _get_plan_admin_row(db, result.id)
        registrar_auditoria(db, "crear_plan", "planes", result.id, {}, plan)
        db.commit()

        return plan
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

        payload_original = _get_plan_admin_row(db, plan_id)
        cambios = datos.model_dump(exclude_none=True)
        service_ids_input = cambios.pop("service_ids", None)

        if cambios:
            db.execute(
                text(
                    f"""
                    UPDATE planes
                    SET {', '.join(f'{campo} = :{campo}' for campo in cambios)}
                    WHERE id = :id
                    """
                ),
                {"id": plan_id, **cambios},
            )

        if service_ids_input is not None:
            service_ids = _validate_service_ids(db, service_ids_input)
            _replace_plan_services(db, plan_id, service_ids)

        actualizado = _get_plan_admin_row(db, plan_id)
        payload_cambios = normalize_mapping(cambios)
        if service_ids_input is not None:
            payload_cambios["service_ids"] = list(service_ids_input)

        _registrar_auditoria_plan(db, plan_id, payload_original, actualizado, payload_cambios)
        db.commit()

        return actualizado
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


def _validate_service_ids(db: Session, service_ids: Iterable[int]) -> list[int]:
    unique_ids = sorted({int(service_id) for service_id in service_ids})
    if not unique_ids:
        return []

    rows = db.execute(
        text("SELECT id FROM services WHERE id = ANY(:ids)"),
        {"ids": unique_ids},
    ).fetchall()
    found_ids = sorted(row.id for row in rows)

    if found_ids != unique_ids:
        raise HTTPException(status_code=400, detail="Hay servicios seleccionados que ya no existen.")

    return unique_ids


def _replace_plan_services(db: Session, plan_id: int, service_ids: list[int]) -> None:
    db.execute(text("DELETE FROM plan_services WHERE plan_id = :plan_id"), {"plan_id": plan_id})
    if not service_ids:
        return

    for service_id in service_ids:
        db.execute(
            text(
                """
                INSERT INTO plan_services (plan_id, service_id)
                VALUES (:plan_id, :service_id)
                """
            ),
            {"plan_id": plan_id, "service_id": service_id},
        )


def _attach_services_to_plans(db: Session, plans: list[dict[str, Any]], plan_ids: list[int]):
    if not plan_ids:
        return plans

    services_by_plan = defaultdict(list)
    service_ids_by_plan = defaultdict(list)

    rows = db.execute(
        text(
            f"""
            SELECT ps.plan_id, {SERVICE_FIELDS_SQL}
            FROM plan_services ps
            JOIN services s ON s.id = ps.service_id
            WHERE ps.plan_id = ANY(:plan_ids)
            ORDER BY ps.plan_id ASC, s.orden_display ASC NULLS LAST, s.nombre ASC
            """
        ),
        {"plan_ids": plan_ids},
    ).fetchall()

    for row in rows:
        service_payload = {
            "id": row.id,
            "code": row.code,
            "nombre": row.nombre,
            "descripcion": row.descripcion,
            "proveedor": row.proveedor,
            "access_mode": row.access_mode,
            "access_instructions": row.access_instructions,
            "cta_label": row.cta_label,
            "cta_url": row.cta_url,
            "activo": row.activo,
        }
        services_by_plan[row.plan_id].append(service_payload)
        service_ids_by_plan[row.plan_id].append(row.id)

    for plan in plans:
        plan["services"] = services_by_plan.get(plan["id"], [])
        plan["service_ids"] = service_ids_by_plan.get(plan["id"], [])

    return plans


def _get_plan_admin_row(db: Session, plan_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT p.id, p.nombre, p.descripcion, p.tipo, p.precio_mensual,
                   p.precio_anual, p.max_beneficiarios, p.activo, p.badge,
                   p.orden_display, p.created_at
            FROM planes p
            WHERE p.id = :id
            """
        ),
        {"id": plan_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    return _attach_services_to_plans(db, [row_to_dict(row)], [plan_id])[0]


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
