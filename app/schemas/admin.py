from typing import Optional

from pydantic import BaseModel


class ActualizarPlan(BaseModel):
    activo: Optional[bool] = None
    precio_mensual: Optional[float] = None


class CambiarEstadoUsuario(BaseModel):
    activo: bool
    motivo: Optional[str] = None


class CambiarRolUsuario(BaseModel):
    rol: str


class CambiarEstadoSuscripcion(BaseModel):
    estado: str
    motivo: Optional[str] = None
