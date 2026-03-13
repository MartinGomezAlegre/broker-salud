from pydantic import BaseModel
from typing import Optional

class PlanRespuesta (BaseModel):
    id: int
    nombre: str
    descripcion: str
    precio_mensual: float
    max_beneficiarios: Optional[int] = None

    class Config:
            from_attributes = True