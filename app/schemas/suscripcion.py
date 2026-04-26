from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

from app.schemas.planes import ServiceResumen

class SuscripcionCrear(BaseModel):
    plan_id: int
    beneficiarios: List[str] = Field(default_factory=list)
    referral_code: Optional[str] = None

class SuscripcionRespuesta(BaseModel):
    id: int
    plan_id: int
    estado: str
    fecha_inicio: date
    precio_pagado: float
    nombre_plan: Optional[str] = None
    descripcion_plan: Optional[str] = None
    fue_exportado: Optional[bool] = None
    fecha_vencimiento: Optional[date] = None
    max_beneficiarios: Optional[int] = None
    tipo_plan: Optional[str] = None
    services: List[ServiceResumen] = Field(default_factory=list)

    class Config:
        from_attributes = True
