from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

ESTADOS_VIGENTES = ("activa", "pendiente_pago", "cancelacion_programada")
CICLO_DIAS = 30
_fecha_vencimiento_checked = False


def normalizar_max_beneficiarios(
    tipo_plan: str | None,
    max_beneficiarios: int | None,
) -> int | None:
    if max_beneficiarios is None:
        return None

    tipo = (tipo_plan or "").lower()
    if tipo == "familiar":
        return min(max_beneficiarios, 4)

    return max_beneficiarios


def ensure_fecha_vencimiento(db: Session) -> None:
    global _fecha_vencimiento_checked
    if _fecha_vencimiento_checked:
        return

    existe = db.execute(text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'suscripciones'
          AND column_name = 'fecha_vencimiento'
        LIMIT 1
    """)).fetchone()
    if not existe:
        raise HTTPException(
            status_code=503,
            detail="Falta la migracion de base de datos para fecha_vencimiento en suscripciones",
        )

    _fecha_vencimiento_checked = True


def ciclo_inicial() -> tuple[date, date]:
    fecha_inicio = date.today()
    fecha_vencimiento = fecha_inicio + timedelta(days=CICLO_DIAS)
    return fecha_inicio, fecha_vencimiento
