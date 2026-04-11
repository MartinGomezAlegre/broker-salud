from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


EstadoComercial = Literal["activo", "inactivo"]
TipoComision = Literal["porcentaje", "fijo"]
TipoDestinatario = Literal["broker", "direct_seller"]


class BrokerCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    contacto: str | None = Field(default=None, max_length=160)
    comision_tipo: TipoComision
    comision_valor: float = Field(gt=0)
    estado: EstadoComercial = "activo"
    usuario_id: int | None = None


class BrokerActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    contacto: str | None = Field(default=None, max_length=160)
    comision_tipo: TipoComision | None = None
    comision_valor: float | None = Field(default=None, gt=0)
    estado: EstadoComercial | None = None
    usuario_id: int | None = None


class BrokerSellerCrear(BaseModel):
    broker_id: int
    nombre: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    referral_code: str | None = Field(default=None, max_length=40)
    estado: EstadoComercial = "activo"
    usuario_id: int | None = None


class BrokerSellerActualizar(BaseModel):
    broker_id: int | None = None
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=5, max_length=180)
    referral_code: str | None = Field(default=None, max_length=40)
    estado: EstadoComercial | None = None
    usuario_id: int | None = None


class DirectSellerCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    referral_code: str | None = Field(default=None, max_length=40)
    comision_tipo: TipoComision
    comision_valor: float = Field(gt=0)
    estado: EstadoComercial = "activo"
    usuario_id: int | None = None


class DirectSellerActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=5, max_length=180)
    referral_code: str | None = Field(default=None, max_length=40)
    comision_tipo: TipoComision | None = None
    comision_valor: float | None = Field(default=None, gt=0)
    estado: EstadoComercial | None = None
    usuario_id: int | None = None


class LiquidacionCrear(BaseModel):
    destinatario_tipo: TipoDestinatario
    destinatario_id: int
    monto: float = Field(gt=0)
    periodo_desde: date | None = None
    periodo_hasta: date | None = None
    notas: str | None = Field(default=None, max_length=400)
