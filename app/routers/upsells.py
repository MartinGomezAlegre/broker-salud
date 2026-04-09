import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.routers.admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upsells", tags=["upsells"])
admin_router = APIRouter(prefix="/admin/upsells", tags=["upsells-admin"])
ESTADOS_UPSELL_SEGURO = {"nuevo", "contactado", "aceptado", "rechazado", "descartado"}


class UpsellSeguroCrear(BaseModel):
    acepta: bool = True


class UpsellSeguroActualizar(BaseModel):
    estado: str
    nota_admin: Optional[str] = None


def _precio_seguro(max_beneficiarios: int | None, tipo_plan: str | None) -> float:
    if (tipo_plan or "").lower() == "familiar" or (max_beneficiarios or 1) > 1:
        return 15000.0
    return 10000.0


def _ensure_upsells_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS upsells_seguro (
                id SERIAL PRIMARY KEY,
                usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                suscripcion_id INT NOT NULL REFERENCES suscripciones(id) ON DELETE CASCADE,
                plan_nombre VARCHAR(120) NOT NULL,
                precio_ofertado NUMERIC(12,2) NOT NULL,
                estado VARCHAR(30) NOT NULL DEFAULT 'nuevo',
                nota_admin TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
    )
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_upsells_seguro_estado ON upsells_seguro(estado)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_upsells_seguro_usuario ON upsells_seguro(usuario_id)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_upsells_seguro_suscripcion ON upsells_seguro(suscripcion_id)"))
    db.commit()


@router.get("/seguro/mio")
def mi_upsell_seguro(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        _ensure_upsells_table(db)
        row = db.execute(
            text(
                """
                SELECT id, usuario_id, suscripcion_id, plan_nombre, precio_ofertado,
                       estado, nota_admin, created_at, updated_at
                FROM upsells_seguro
                WHERE usuario_id = :usuario_id
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id},
        ).fetchone()

        if not row:
            return None

        return {
            "id": row.id,
            "usuario_id": row.usuario_id,
            "suscripcion_id": row.suscripcion_id,
            "plan_nombre": row.plan_nombre,
            "precio_ofertado": float(row.precio_ofertado),
            "estado": row.estado,
            "nota_admin": row.nota_admin,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en mi_upsell_seguro: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("/seguro")
def crear_upsell_seguro(
    datos: UpsellSeguroCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        _ensure_upsells_table(db)
        suscripcion = db.execute(
            text(
                """
                SELECT s.id, p.nombre AS plan_nombre, p.max_beneficiarios, p.tipo
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                WHERE s.usuario_id = :usuario_id
                  AND s.estado IN ('activa', 'cancelacion_programada', 'pendiente_pago')
                ORDER BY COALESCE(s.fecha_vencimiento, s.created_at) DESC, s.created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id},
        ).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=400, detail="Necesitas una suscripcion iniciada para solicitar el seguro medico")

        precio = _precio_seguro(suscripcion.max_beneficiarios, suscripcion.tipo)

        existente = db.execute(
            text(
                """
                SELECT id
                FROM upsells_seguro
                WHERE usuario_id = :usuario_id
                  AND suscripcion_id = :suscripcion_id
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id, "suscripcion_id": suscripcion.id},
        ).fetchone()

        if existente:
            row = db.execute(
                text(
                    """
                    UPDATE upsells_seguro
                    SET precio_ofertado = :precio_ofertado,
                        estado = :estado,
                        updated_at = NOW()
                    WHERE id = :id
                    RETURNING id, usuario_id, suscripcion_id, plan_nombre, precio_ofertado,
                              estado, nota_admin, created_at, updated_at
                    """
                ),
                {
                    "id": existente.id,
                    "precio_ofertado": precio,
                    "estado": "nuevo" if datos.acepta else "rechazado",
                },
            ).fetchone()
        else:
            row = db.execute(
                text(
                    """
                    INSERT INTO upsells_seguro
                        (usuario_id, suscripcion_id, plan_nombre, precio_ofertado, estado)
                    VALUES
                        (:usuario_id, :suscripcion_id, :plan_nombre, :precio_ofertado, :estado)
                    RETURNING id, usuario_id, suscripcion_id, plan_nombre, precio_ofertado,
                              estado, nota_admin, created_at, updated_at
                    """
                ),
                {
                    "usuario_id": usuario_id,
                    "suscripcion_id": suscripcion.id,
                    "plan_nombre": suscripcion.plan_nombre,
                    "precio_ofertado": precio,
                    "estado": "nuevo" if datos.acepta else "rechazado",
                },
            ).fetchone()

        db.commit()

        return {
            "id": row.id,
            "usuario_id": row.usuario_id,
            "suscripcion_id": row.suscripcion_id,
            "plan_nombre": row.plan_nombre,
            "precio_ofertado": float(row.precio_ofertado),
            "estado": row.estado,
            "nota_admin": row.nota_admin,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_upsell_seguro: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@admin_router.get("/seguro")
def listar_upsells_seguro(
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    try:
        _ensure_upsells_table(db)
        if estado and estado not in ESTADOS_UPSELL_SEGURO:
            raise HTTPException(status_code=400, detail="Estado de upsell invalido")

        filtro = "WHERE us.estado = :estado" if estado else ""
        params = {"estado": estado} if estado else {}
        rows = db.execute(
            text(
                f"""
                SELECT us.id, us.usuario_id, us.suscripcion_id, us.plan_nombre, us.precio_ofertado,
                       us.estado, us.nota_admin, us.created_at, us.updated_at,
                       u.nombre || ' ' || u.apellido AS usuario_nombre,
                       u.email AS usuario_email
                FROM upsells_seguro us
                JOIN usuarios u ON u.id = us.usuario_id
                {filtro}
                ORDER BY us.updated_at DESC NULLS LAST, us.created_at DESC
                """
            ),
            params,
        ).fetchall()

        return [
            {
                "id": row.id,
                "usuario_id": row.usuario_id,
                "suscripcion_id": row.suscripcion_id,
                "plan_nombre": row.plan_nombre,
                "precio_ofertado": float(row.precio_ofertado),
                "estado": row.estado,
                "nota_admin": row.nota_admin,
                "usuario_nombre": row.usuario_nombre,
                "usuario_email": row.usuario_email,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_upsells_seguro: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@admin_router.put("/seguro/{upsell_id}")
def actualizar_upsell_seguro(
    upsell_id: int,
    datos: UpsellSeguroActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    try:
        _ensure_upsells_table(db)
        if datos.estado not in ESTADOS_UPSELL_SEGURO:
            raise HTTPException(status_code=400, detail="Estado de upsell invalido")

        row = db.execute(
            text("SELECT id FROM upsells_seguro WHERE id = :id"),
            {"id": upsell_id},
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Upsell no encontrado")

        actualizado = db.execute(
            text(
                """
                UPDATE upsells_seguro
                SET estado = :estado,
                    nota_admin = :nota_admin,
                    updated_at = NOW()
                WHERE id = :id
                RETURNING id, estado, nota_admin, updated_at
                """
            ),
            {"id": upsell_id, "estado": datos.estado, "nota_admin": datos.nota_admin},
        ).fetchone()
        db.commit()

        return {
            "id": actualizado.id,
            "estado": actualizado.estado,
            "nota_admin": actualizado.nota_admin,
            "updated_at": actualizado.updated_at.isoformat() if actualizado.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en actualizar_upsell_seguro: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
