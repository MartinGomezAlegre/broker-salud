from pydantic import BaseModel, Field
from typing import Optional


class ServiceResumen(BaseModel):
    id: int
    code: str
    nombre: str
    descripcion: str
    proveedor: str
    access_mode: Optional[str] = None
    access_instructions: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    activo: Optional[bool] = None

    class Config:
        from_attributes = True

class PlanRespuesta(BaseModel):
    id: int
    nombre: str
    descripcion: str
    precio_mensual: float
    max_beneficiarios: Optional[int] = None
    activo: Optional[bool] = None
    tipo: Optional[str] = None
    badge: Optional[str] = None
    services: list[ServiceResumen] = Field(default_factory=list)

    class Config:
        from_attributes = True
