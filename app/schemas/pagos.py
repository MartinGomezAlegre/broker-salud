from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PagoIntentoCrear(BaseModel):
    suscripcion_id: int = Field(gt=0)
    proveedor: Literal["mercadopago"] = "mercadopago"


class PagoIntentoRespuesta(BaseModel):
    id: int
    suscripcion_id: int
    usuario_id: int
    proveedor: str
    external_reference: str
    estado: str
    monto: float
    moneda: str
    checkout_url: str | None = None
    created_at: datetime
    updated_at: datetime


class EstadoPagoRespuesta(BaseModel):
    suscripcion_id: int
    estado_suscripcion: str
    intento: dict | None = None
    pago: dict | None = None
    pago_procesado: dict | None = None


class WebhookMercadoPagoAck(BaseModel):
    ok: bool
    accepted: bool
    webhook_id: int
    queued: bool
