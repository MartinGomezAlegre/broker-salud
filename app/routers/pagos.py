from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.schemas.pagos import (
    EstadoPagoRespuesta,
    PagoIntentoCrear,
    PagoIntentoRespuesta,
    WebhookMercadoPagoAck,
)
from app.services.pagos import (
    crear_intento_pago,
    despachar_procesamiento_webhook_mercadopago,
    estado_pago_suscripcion,
    registrar_webhook_mercadopago,
)

router = APIRouter(prefix="/pagos", tags=["pagos"])
public_router = APIRouter(prefix="/webhooks", tags=["pagos"])


@router.post("/intentos", response_model=PagoIntentoRespuesta)
def crear_intento_pago_route(
    datos: PagoIntentoCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return crear_intento_pago(
        db=db,
        usuario_id=usuario_id,
        suscripcion_id=datos.suscripcion_id,
        proveedor=datos.proveedor,
    )


@router.get("/suscripciones/{suscripcion_id}/estado", response_model=EstadoPagoRespuesta)
def estado_pago_suscripcion_route(
    suscripcion_id: int,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return estado_pago_suscripcion(db, usuario_id, suscripcion_id)


@public_router.post("/mercadopago", response_model=WebhookMercadoPagoAck)
async def mercadopago_webhook_route(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(None),
    x_request_id: str | None = Header(None),
):
    webhook_id, accepted = await registrar_webhook_mercadopago(
        db=db,
        request=request,
        signature_header=x_signature,
        request_id=x_request_id,
    )
    queued = False
    if accepted:
        queued = despachar_procesamiento_webhook_mercadopago(background_tasks, webhook_id)

    return {
        "ok": True,
        "accepted": accepted,
        "webhook_id": webhook_id,
        "queued": queued,
    }
