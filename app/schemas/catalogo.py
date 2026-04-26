from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class PlanCrear(BaseModel):
    nombre: str
    descripcion: str
    tipo: Optional[str] = None
    precio_mensual: float
    precio_anual: Optional[float] = None
    max_beneficiarios: Optional[int] = None
    badge: Optional[str] = None
    orden_display: Optional[int] = None
    activo: bool = True
    service_ids: list[int] = Field(default_factory=list)


class PlanActualizar(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    tipo: Optional[str] = None
    precio_mensual: Optional[float] = None
    precio_anual: Optional[float] = None
    max_beneficiarios: Optional[int] = None
    badge: Optional[str] = None
    orden_display: Optional[int] = None
    activo: Optional[bool] = None
    service_ids: Optional[list[int]] = None


class PlanOrden(BaseModel):
    orden_display: int


class ServiceCrear(BaseModel):
    nombre: str
    code: str
    descripcion: Optional[str] = None
    proveedor: str
    access_mode: Optional[str] = None
    access_instructions: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    activo: bool = True


class CuponCrear(BaseModel):
    codigo: str
    descripcion: Optional[str] = None
    tipo_descuento: str
    valor: float
    plan_id: Optional[int] = None
    max_usos: Optional[int] = None
    valido_desde: Optional[date] = None
    valido_hasta: Optional[date] = None
    solo_nuevos_usuarios: bool = False


class CuponActualizar(BaseModel):
    descripcion: Optional[str] = None
    tipo_descuento: Optional[str] = None
    valor: Optional[float] = None
    plan_id: Optional[int] = None
    max_usos: Optional[int] = None
    valido_desde: Optional[date] = None
    valido_hasta: Optional[date] = None
    solo_nuevos_usuarios: Optional[bool] = None


class CuponEstado(BaseModel):
    activo: bool
