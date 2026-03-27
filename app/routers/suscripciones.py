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

@router.post("", response_model=SuscripcionRespuesta)
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

    # 2. Verificar que no tiene suscripción activa o pendiente de pago
    suscripcion_existente = db.execute(
        text("""SELECT id FROM suscripciones
                WHERE usuario_id = :usuario_id
                AND estado IN ('activa', 'pendiente_pago')"""),
        {"usuario_id": usuario_id}
    ).fetchone()

    if suscripcion_existente:
        raise HTTPException(status_code=400, detail="Ya tenés una suscripción activa o pendiente de pago")

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

@router.get("/mia")
def mi_suscripcion(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    suscripcion = db.execute(
        text("""SELECT s.*, p.nombre AS nombre_plan,
                       p.descripcion AS descripcion_plan
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                WHERE s.usuario_id = :usuario_id
                  AND s.estado != 'cancelada'
                ORDER BY s.created_at DESC LIMIT 1"""),
        {"usuario_id": usuario_id}
    ).fetchone()

    if not suscripcion:
        raise HTTPException(status_code=404, detail="No tenés suscripciones activas")

    # Verificar si fue exportada a Mediquo
    exportado = db.execute(
        text("""SELECT COUNT(*) as cnt FROM auditoria
                WHERE accion = 'exportado_a_mediquo'
                  AND datos_nuevos::text LIKE '%' || :sid || '%'"""),
        {"sid": str(suscripcion.id)}
    ).fetchone()

    return {
        "id": suscripcion.id,
        "plan_id": suscripcion.plan_id,
        "estado": suscripcion.estado,
        "fecha_inicio": suscripcion.fecha_inicio.isoformat() if suscripcion.fecha_inicio else None,
        "precio_pagado": float(suscripcion.precio_pagado) if suscripcion.precio_pagado is not None else None,
        "nombre_plan": suscripcion.nombre_plan,
        "descripcion_plan": suscripcion.descripcion_plan,
        "fue_exportado": exportado.cnt > 0,
    }