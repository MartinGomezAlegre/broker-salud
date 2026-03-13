from pydantic import BaseModel
from datetime import date

class UsuarioCrear(BaseModel):
    nombre: str
    apellido: str
    email: str
    telefono: str
    fecha_nacimiento: date
    contrasenia: str

class UsuarioRespuesta(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str

    class Config:
        from_attributes = True