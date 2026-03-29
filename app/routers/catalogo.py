import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.routers.admin import require_admin
from datetime import date
import json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/catalogo",
    tags=["catalogo"]
)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class PlanCrear(BaseModel):
    nombre: str
    descripcion: str
    tipo: Optional[str] = None
    precio_mensual: float
    precio_anual: Optional[float] = None
    max_beneficiarios: Optional[int] = None
    badge: Optional[str] = None
    orden_display: Optional[int] = None
    proveedor_id: Optional[int] = None


class PlanActualizar(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    tipo: Optional[str] = None
    precio_mensual: Optional[float] = None
    precio_anual: Optional[float] = None
    max_beneficiarios: Optional[int] = None
    badge: Optional[str] = None
    orden_display: Optional[int] = None
    activo: Optional[bool] = None


class PlanOrden(BaseModel):
    orden_display: int


class CuponCrear(BaseModel):
    codigo: str
    descripcion: Optional[str] = None
    tipo_descuento: str
    valor: float
    plan_id: Optional[int] = None
    max_usos: Optional[int] = None
    valido_desde: date
    valido_hasta: date
    solo_nuevos_usuarios: bool = False


class CuponActualizar(BaseModel):
    descripcion: Optional[str] = None
    tipo_descuento: Optional[str] = None
    valor: Optional[float] = None
    plan_id: Optional[int] = None
    max_usos: Optional[int] = None
    valido_desde: Optional[date] = None
    valido_hasta: Optional[date] = None
    solo_nuevos_usuarios: Optional[bool] = None


class CuponEstado(BaseModel):
    activo: bool


def _registrar_auditoria(db: Session, accion: str, tabla: str, registro_id: int,
                          datos_anteriores: dict, datos_nuevos: dict):
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


# ─── Planes ───────────────────────────────────────────────────────────────────

@router.get("/planes")
def listar_planes_admin(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
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
                "id": r.id,
                "nombre": r.nombre,
                "descripcion": r.descripcion,
                "tipo": r.tipo,
                "precio_mensual": float(r.precio_mensual) if r.precio_mensual else None,
                "precio_anual": float(r.precio_anual) if r.precio_anual else None,
                "max_beneficiarios": r.max_beneficiarios,
                "activo": r.activo,
                "badge": r.badge,
                "orden_display": r.orden_display,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "suscriptores_activos": r.suscriptores_activos or 0,
                "revenue_mensual": round(
                    (r.suscriptores_activos or 0) * float(r.precio_mensual or 0), 2
                ),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("/planes")
def crear_plan(
    datos: PlanCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
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
        """), {
            "nombre": datos.nombre,
            "descripcion": datos.descripcion,
            "tipo": datos.tipo,
            "precio_mensual": datos.precio_mensual,
            "precio_anual": datos.precio_anual,
            "max_beneficiarios": datos.max_beneficiarios,
            "badge": datos.badge,
            "orden_display": datos.orden_display,
        }).fetchone()
        db.commit()

        plan = db.execute(
            text("SELECT * FROM planes WHERE id = :id"), {"id": result.id}
        ).fetchone()
        return {k: (float(v) if isinstance(v, type(plan.precio_mensual)) and v is not None
                    else (v.isoformat() if hasattr(v, "isoformat") else v))
                for k, v in plan._mapping.items()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.put("/planes/{plan_id}")
def actualizar_plan_catalogo(
    plan_id: int,
    datos: PlanActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        plan = db.execute(
            text("SELECT * FROM planes WHERE id = :id"), {"id": plan_id}
        ).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        campos = []
        params = {"id": plan_id}
        cambios = datos.model_dump(exclude_none=True)

        precio_anterior = None
        if "precio_mensual" in cambios:
            precio_anterior = float(plan.precio_mensual) if plan.precio_mensual else None

        for campo, valor in cambios.items():
            campos.append(f"{campo} = :{campo}")
            params[campo] = valor

        if campos:
            db.execute(
                text(f"UPDATE planes SET {', '.join(campos)} WHERE id = :id"), params
            )
            if precio_anterior is not None:
                _registrar_auditoria(db, "cambio_precio_plan", "planes", plan_id,
                                     {"precio_mensual": precio_anterior},
                                     {"precio_mensual": cambios["precio_mensual"]})
            db.commit()

        actualizado = db.execute(
            text("SELECT * FROM planes WHERE id = :id"), {"id": plan_id}
        ).fetchone()
        return {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                for k, v in actualizado._mapping.items()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.put("/planes/{plan_id}/orden")
def actualizar_orden_plan(
    plan_id: int,
    datos: PlanOrden,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        plan = db.execute(
            text("SELECT id FROM planes WHERE id = :id"), {"id": plan_id}
        ).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        db.execute(
            text("UPDATE planes SET orden_display = :orden WHERE id = :id"),
            {"orden": datos.orden_display, "id": plan_id}
        )
        db.commit()
        return {"id": plan_id, "orden_display": datos.orden_display}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ─── Cupones ──────────────────────────────────────────────────────────────────

@router.get("/cupones")
def listar_cupones(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        rows = db.execute(text("""
            SELECT c.id, c.codigo, c.descripcion, c.tipo_descuento, c.valor,
                   p.nombre AS plan_nombre,
                   c.max_usos, c.usos_actuales, c.valido_desde, c.valido_hasta,
                   c.solo_nuevos_usuarios, c.activo, c.created_at
            FROM cupones c
            LEFT JOIN planes p ON p.id = c.plan_id
            ORDER BY c.created_at DESC
        """)).fetchall()

        return [
            {
                "id": r.id,
                "codigo": r.codigo,
                "descripcion": r.descripcion,
                "tipo_descuento": r.tipo_descuento,
                "valor": float(r.valor) if r.valor is not None else None,
                "plan_nombre": r.plan_nombre,
                "max_usos": r.max_usos,
                "usos_actuales": r.usos_actuales,
                "valido_desde": r.valido_desde.isoformat() if r.valido_desde else None,
                "valido_hasta": r.valido_hasta.isoformat() if r.valido_hasta else None,
                "solo_nuevos": r.solo_nuevos_usuarios,
                "activo": r.activo,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("/cupones")
def crear_cupon(
    datos: CuponCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        existente = db.execute(
            text("SELECT id FROM cupones WHERE codigo = :codigo"), {"codigo": datos.codigo}
        ).fetchone()
        if existente:
            raise HTTPException(status_code=400, detail="El código de cupón ya existe")

        result = db.execute(text("""
            INSERT INTO cupones
              (codigo, descripcion, tipo_descuento, valor, plan_id, max_usos,
               usos_actuales, valido_desde, valido_hasta, solo_nuevos_usuarios, activo)
            VALUES
              (:codigo, :descripcion, :tipo_descuento, :valor, :plan_id, :max_usos,
               0, :valido_desde, :valido_hasta, :solo_nuevos_usuarios, true)
            RETURNING id
        """), {
            "codigo": datos.codigo,
            "descripcion": datos.descripcion,
            "tipo_descuento": datos.tipo_descuento,
            "valor": datos.valor,
            "plan_id": datos.plan_id,
            "max_usos": datos.max_usos,
            "valido_desde": datos.valido_desde,
            "valido_hasta": datos.valido_hasta,
            "solo_nuevos_usuarios": datos.solo_nuevos_usuarios,
        }).fetchone()
        db.commit()

        cupon = db.execute(
            text("SELECT * FROM cupones WHERE id = :id"), {"id": result.id}
        ).fetchone()
        return {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                for k, v in cupon._mapping.items()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.put("/cupones/{cupon_id}")
def actualizar_cupon(
    cupon_id: int,
    datos: CuponActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        cupon = db.execute(
            text("SELECT id FROM cupones WHERE id = :id"), {"id": cupon_id}
        ).fetchone()
        if not cupon:
            raise HTTPException(status_code=404, detail="Cupón no encontrado")

        campos = []
        params = {"id": cupon_id}
        for campo, valor in datos.model_dump(exclude_none=True).items():
            if campo == "codigo":
                continue  # no permitir cambiar el código
            campos.append(f"{campo} = :{campo}")
            params[campo] = valor

        if campos:
            db.execute(
                text(f"UPDATE cupones SET {', '.join(campos)} WHERE id = :id"), params
            )
            db.commit()

        actualizado = db.execute(
            text("SELECT * FROM cupones WHERE id = :id"), {"id": cupon_id}
        ).fetchone()
        return {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                for k, v in actualizado._mapping.items()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.put("/cupones/{cupon_id}/estado")
def cambiar_estado_cupon(
    cupon_id: int,
    datos: CuponEstado,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        cupon = db.execute(
            text("SELECT id FROM cupones WHERE id = :id"), {"id": cupon_id}
        ).fetchone()
        if not cupon:
            raise HTTPException(status_code=404, detail="Cupón no encontrado")

        db.execute(
            text("UPDATE cupones SET activo = :activo WHERE id = :id"),
            {"activo": datos.activo, "id": cupon_id}
        )
        db.commit()
        return {"id": cupon_id, "activo": datos.activo}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.delete("/cupones/{cupon_id}")
def eliminar_cupon(
    cupon_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        cupon = db.execute(
            text("SELECT id, usos_actuales FROM cupones WHERE id = :id"), {"id": cupon_id}
        ).fetchone()
        if not cupon:
            raise HTTPException(status_code=404, detail="Cupón no encontrado")

        if cupon.usos_actuales and cupon.usos_actuales > 0:
            db.execute(
                text("UPDATE cupones SET activo = false WHERE id = :id"), {"id": cupon_id}
            )
            db.commit()
            return {"mensaje": "El cupón tiene usos registrados, fue desactivado en lugar de eliminado"}

        db.execute(text("DELETE FROM cupones WHERE id = :id"), {"id": cupon_id})
        db.commit()
        return {"mensaje": "Cupón eliminado correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/cupones/{cupon_id}/usos")
def usos_cupon(
    cupon_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        cupon = db.execute(
            text("SELECT id FROM cupones WHERE id = :id"), {"id": cupon_id}
        ).fetchone()
        if not cupon:
            raise HTTPException(status_code=404, detail="Cupón no encontrado")

        rows = db.execute(text("""
            SELECT u.nombre || ' ' || u.apellido AS nombre_usuario,
                   u.email,
                   p.nombre AS plan_contratado,
                   cu.descuento_aplicado,
                   cu.created_at AS fecha_uso
            FROM cupones_uso cu
            JOIN usuarios u ON u.id = cu.usuario_id
            LEFT JOIN suscripciones s ON s.id = cu.suscripcion_id
            LEFT JOIN planes p ON p.id = s.plan_id
            WHERE cu.cupon_id = :cupon_id
            ORDER BY cu.created_at DESC
        """), {"cupon_id": cupon_id}).fetchall()

        return [
            {
                "nombre_usuario": r.nombre_usuario,
                "email": r.email,
                "plan_contratado": r.plan_contratado,
                "descuento_aplicado": float(r.descuento_aplicado) if r.descuento_aplicado else None,
                "fecha_uso": r.fecha_uso.isoformat() if r.fecha_uso else None,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
