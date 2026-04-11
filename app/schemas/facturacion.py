from typing import List, Optional

from pydantic import BaseModel


class PagoManual(BaseModel):
    usuario_id: int
    plan_id: int
    monto: float
    metodo: str
    descripcion: Optional[str] = None


class MarcarExportados(BaseModel):
    suscripcion_ids: List[int]
