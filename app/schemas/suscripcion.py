from pydantic import BaseModel
from typing import List
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

    class Config:
        from_attributes = True  