import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ESTADOS_UPSELL_SEGURO = {"nuevo", "contactado", "aceptado", "rechazado", "descartado"}
_upsells_checked = False


def precio_seguro(max_beneficiarios: int | None, tipo_plan: str | None) -> float:
    if (tipo_plan or "").lower() == "familiar" or (max_beneficiarios or 1) > 1:
        return 15000.0
    return 10000.0


def ensure_upsells_table(db: Session) -> None:
    global _upsells_checked
    if _upsells_checked:
        return

    existe = db.execute(text("""
        SELECT to_regclass('public.upsells_seguro') AS tabla
    """)).fetchone()
    if not existe or not existe.tabla:
        raise HTTPException(
            status_code=503,
            detail="Falta una migracion de Alembic para upsells_seguro. Ejecuta alembic upgrade head.",
        )

    _upsells_checked = True


def serialize_upsell(row) -> dict:
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


def validate_estado(estado: str) -> None:
    if estado not in ESTADOS_UPSELL_SEGURO:
        raise HTTPException(status_code=400, detail="Estado de upsell invalido")
