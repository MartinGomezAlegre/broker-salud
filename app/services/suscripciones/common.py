from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

ESTADOS_VIGENTES = ("activa", "pendiente_pago", "cancelacion_programada")
CICLO_DIAS = 30
_fecha_vencimiento_checked = False


def normalizar_tipo_plan(tipo_plan: str | None) -> str:
    return (tipo_plan or "").strip().lower().replace("-", "_").replace(" ", "_")


def es_plan_familiar(tipo_plan: str | None) -> bool:
    return "familiar" in normalizar_tipo_plan(tipo_plan)


def es_plan_individual(tipo_plan: str | None) -> bool:
    tipo = normalizar_tipo_plan(tipo_plan)
    if es_plan_familiar(tipo):
        return False
    return (
        tipo in {"personal", "individual", "b2c", "b2c_personal", "b2c_individual"}
        or "personal" in tipo
        or "individual" in tipo
    )


def normalizar_max_beneficiarios(
    tipo_plan: str | None,
    max_beneficiarios: int | None,
) -> int | None:
    if es_plan_individual(tipo_plan):
        return 1

    if max_beneficiarios is None:
        return None

    if es_plan_familiar(tipo_plan):
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
            detail="Falta una migracion de Alembic para fecha_vencimiento en suscripciones. Ejecuta alembic upgrade head.",
        )

    _fecha_vencimiento_checked = True


def ciclo_inicial() -> tuple[date, date]:
    fecha_inicio = date.today()
    fecha_vencimiento = fecha_inicio + timedelta(days=CICLO_DIAS)
    return fecha_inicio, fecha_vencimiento


def sincronizar_vencimientos_usuario(db: Session, usuario_id: int) -> None:
    ensure_fecha_vencimiento(db)
    result = db.execute(
        text(
            """
            UPDATE suscripciones
            SET estado = CASE
                WHEN estado = 'cancelacion_programada' THEN 'cancelada'
                ELSE 'vencida'
            END
            WHERE usuario_id = :usuario_id
              AND estado IN ('activa', 'cancelacion_programada')
              AND fecha_vencimiento IS NOT NULL
              AND fecha_vencimiento < CURRENT_DATE
            """
        ),
        {"usuario_id": usuario_id},
    )
    if result.rowcount:
        db.commit()


def tiene_suscripcion_activa(db: Session, usuario_id: int) -> bool:
    sincronizar_vencimientos_usuario(db, usuario_id)
    row = db.execute(
        text(
            """
            SELECT id
            FROM suscripciones
            WHERE usuario_id = :usuario_id
              AND estado IN ('activa', 'cancelacion_programada')
              AND (fecha_vencimiento IS NULL OR fecha_vencimiento >= CURRENT_DATE)
            LIMIT 1
            """
        ),
        {"usuario_id": usuario_id},
    ).fetchone()
    return bool(row)


def require_suscripcion_activa(db: Session, usuario_id: int) -> None:
    if not tiene_suscripcion_activa(db, usuario_id):
        raise HTTPException(
            status_code=402,
            detail="Tu plan esta vencido o pendiente de renovacion. Renova el plan para acceder a este servicio.",
        )
