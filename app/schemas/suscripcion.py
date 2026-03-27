from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class SuscripcionCrear(BaseModel):
    plan_id: int
    beneficiarios: List[str] = []

class SuscripcionRespuesta(BaseModel):
    id: int
    plan_id: int
    estado: str
    fecha_inicio: date
    precio_pagado: float
    nombre_plan: Optional[str] = None
    descripcion_plan: Optional[str] = None
    fue_exportado: Optional[bool] = None

    class Config:
        from_attributes = True