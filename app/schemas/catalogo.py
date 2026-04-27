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


class MedicamentoCrear(BaseModel):
    nombre: str
    principio_activo: Optional[str] = None
    presentacion: Optional[str] = None
    laboratorio: Optional[str] = None
    descripcion: Optional[str] = None
    cobertura_resumen: Optional[str] = None
    descuento_porcentaje: Optional[int] = Field(default=None, ge=0, le=100)
    keywords: Optional[str] = None
    activo: bool = True
    orden_display: Optional[int] = None


class MedicamentoActualizar(BaseModel):
    nombre: Optional[str] = None
    principio_activo: Optional[str] = None
    presentacion: Optional[str] = None
    laboratorio: Optional[str] = None
    descripcion: Optional[str] = None
    cobertura_resumen: Optional[str] = None
    descuento_porcentaje: Optional[int] = Field(default=None, ge=0, le=100)
    keywords: Optional[str] = None
    activo: Optional[bool] = None
    orden_display: Optional[int] = None


class FarmaciaCrear(BaseModel):
    nombre: str
    direccion: str
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    horario: Optional[str] = None
    estado_atencion: Optional[str] = None
    distancia_km: Optional[float] = Field(default=None, ge=0)
    descuento_porcentaje: Optional[int] = Field(default=None, ge=0, le=100)
    maps_url: Optional[str] = None
    descripcion: Optional[str] = None
    activo: bool = True
    orden_display: Optional[int] = None


class FarmaciaActualizar(BaseModel):
    nombre: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    horario: Optional[str] = None
    estado_atencion: Optional[str] = None
    distancia_km: Optional[float] = Field(default=None, ge=0)
    descuento_porcentaje: Optional[int] = Field(default=None, ge=0, le=100)
    maps_url: Optional[str] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None
    orden_display: Optional[int] = None


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
