from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.security.passwords import validate_password_strength


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
    access_email: str | None = Field(default=None, max_length=180)
    access_password: str | None = Field(default=None, min_length=10, max_length=120)

    @field_validator("access_password")
    @classmethod
    def validar_access_password(cls, value: str | None):
        if value is None or not value.strip():
            return None
        return validate_password_strength(value)


class BrokerActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    contacto: str | None = Field(default=None, max_length=160)
    comision_tipo: TipoComision | None = None
    comision_valor: float | None = Field(default=None, gt=0)
    estado: EstadoComercial | None = None
    usuario_id: int | None = None
    access_email: str | None = Field(default=None, max_length=180)
    access_password: str | None = Field(default=None, min_length=10, max_length=120)

    @field_validator("access_password")
    @classmethod
    def validar_access_password(cls, value: str | None):
        if value is None or not value.strip():
            return None
        return validate_password_strength(value)


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
    access_email: str | None = Field(default=None, max_length=180)
    access_password: str | None = Field(default=None, min_length=10, max_length=120)

    @field_validator("access_password")
    @classmethod
    def validar_access_password(cls, value: str | None):
        if value is None or not value.strip():
            return None
        return validate_password_strength(value)


class DirectSellerActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=5, max_length=180)
    referral_code: str | None = Field(default=None, max_length=40)
    comision_tipo: TipoComision | None = None
    comision_valor: float | None = Field(default=None, gt=0)
    estado: EstadoComercial | None = None
    usuario_id: int | None = None
    access_email: str | None = Field(default=None, max_length=180)
    access_password: str | None = Field(default=None, min_length=10, max_length=120)

    @field_validator("access_password")
    @classmethod
    def validar_access_password(cls, value: str | None):
        if value is None or not value.strip():
            return None
        return validate_password_strength(value)


class BrokerPortalSellerCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    contrasenia: str = Field(min_length=10, max_length=120)
    referral_code: str | None = Field(default=None, max_length=40)
    estado: EstadoComercial = "activo"

    @field_validator("contrasenia")
    @classmethod
    def validar_contrasenia(cls, value: str):
        return validate_password_strength(value)


class BrokerPortalSellerActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=5, max_length=180)
    nueva_contrasenia: str | None = Field(default=None, min_length=10, max_length=120)
    referral_code: str | None = Field(default=None, max_length=40)
    estado: EstadoComercial | None = None

    @field_validator("nueva_contrasenia")
    @classmethod
    def validar_nueva_contrasenia(cls, value: str | None):
        if value is None or not value.strip():
            return None
        return validate_password_strength(value)


class LiquidacionCrear(BaseModel):
    destinatario_tipo: TipoDestinatario
    destinatario_id: int
    monto: float = Field(gt=0)
    periodo_desde: date | None = None
    periodo_hasta: date | None = None
    notas: str | None = Field(default=None, max_length=400)


class ComercialAcuerdoCrear(BaseModel):
    tipo: str
    titulo: str = Field(min_length=2, max_length=180)
    descripcion: str | None = Field(default=None, max_length=600)
    estado: str | None = Field(default="vigente", max_length=40)
    fecha_firma: date | None = None
    fecha_vencimiento: date | None = None
    archivo_url: str | None = Field(default=None, max_length=400)
    notas: str | None = Field(default=None, max_length=1000)


class ComercialAcuerdoActualizar(BaseModel):
    tipo: str | None = Field(default=None, max_length=40)
    titulo: str | None = Field(default=None, min_length=2, max_length=180)
    descripcion: str | None = Field(default=None, max_length=600)
    estado: str | None = Field(default=None, max_length=40)
    fecha_firma: date | None = None
    fecha_vencimiento: date | None = None
    archivo_url: str | None = Field(default=None, max_length=400)
    notas: str | None = Field(default=None, max_length=1000)
