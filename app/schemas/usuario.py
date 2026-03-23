from pydantic import BaseModel
from typing import Optional
from datetime import date

class UsuarioCrear(BaseModel):
    nombre: str
    apellido: str
    email: str
    telefono: str
    fecha_nacimiento: date
    contrasenia: str
    dni: Optional[str] = None

class UsuarioRespuesta(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    rol: Optional[str] = None
    dni: Optional[str] = None

    class Config:
        from_attributes = True