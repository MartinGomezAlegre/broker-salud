from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.auth import get_current_user
from app.schemas.suscripcion import SuscripcionCrear, SuscripcionRespuesta
from datetime import date

router = APIRouter(
    prefix="/suscripciones",
    tags=["suscripciones"]
)

@router.post("/", response_model=SuscripcionRespuesta)
def contratar_plan(
    datos: SuscripcionCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    # 1. Verificar que el plan existe y está activo
    plan = db.execute(
        text("SELECT * FROM planes WHERE id = :id AND activo = true"),
        {"id": datos.plan_id}
    ).fetchone()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado o inactivo")

    # 2. Verificar que no tiene suscripción activa
    suscripcion_existente = db.execute(
        text("""SELECT id FROM suscripciones 
                WHERE usuario_id = :usuario_id 
                AND estado = 'activa'"""),
        {"usuario_id": usuario_id}
    ).fetchone()

    if suscripcion_existente:
        raise HTTPException(status_code=400, detail="Ya tenés una suscripción activa")

    # 3. Crear la suscripción
    resultado = db.execute(
        text("""INSERT INTO suscripciones 
                (usuario_id, plan_id, estado, fecha_inicio, precio_pagado)
                VALUES (:usuario_id, :plan_id, 'pendiente_pago', :fecha_inicio, :precio_pagado)
                RETURNING *"""),
        {
            "usuario_id": usuario_id,
            "plan_id": datos.plan_id,
            "fecha_inicio": date.today(),
            "precio_pagado": plan.precio_mensual
        }
    ).fetchone()

    db.commit()
    return resultado

@router.get("/mia", response_model=SuscripcionRespuesta)
def mi_suscripcion(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    suscripcion = db.execute(
        text("""SELECT * FROM suscripciones 
                WHERE usuario_id = :usuario_id 
                AND estado != 'cancelada'
                ORDER BY created_at DESC LIMIT 1"""),
        {"usuario_id": usuario_id}
    ).fetchone()

    if not suscripcion:
        raise HTTPException(status_code=404, detail="No tenés suscripciones activas")

    return suscripcion