from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.limiter import limiter
from app.schemas.suscripcion import SuscripcionCrear, SuscripcionRespuesta
from app.services.pagos import estado_pago_suscripcion
from app.services.suscripciones import cancelar_mi_suscripcion, contratar_plan, mi_suscripcion

router = APIRouter(prefix="/suscripciones", tags=["suscripciones"])


@router.post("", response_model=SuscripcionRespuesta)
@limiter.limit("10/hour")
def contratar_plan_route(
    request: Request,
    datos: SuscripcionCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return contratar_plan(db, usuario_id, datos)


@router.get("/mia")
def mi_suscripcion_route(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return mi_suscripcion(db, usuario_id)


@router.put("/mia/cancelar")
def cancelar_mi_suscripcion_route(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return cancelar_mi_suscripcion(db, usuario_id)


@router.get("/{suscripcion_id}/estado-pago")
def estado_pago_route(
    suscripcion_id: int,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return estado_pago_suscripcion(db, usuario_id, suscripcion_id)
