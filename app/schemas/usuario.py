from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import date


class UsuarioCrear(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    telefono: str
    fecha_nacimiento: date
    contrasenia: str
    dni: Optional[str] = None

    @field_validator("contrasenia")
    @classmethod
    def validar_contrasenia(cls, v):
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v

    @field_validator("nombre", "apellido")
    @classmethod
    def validar_nombre(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Debe tener al menos 2 caracteres")
        return v.strip()


class UsuarioRespuesta(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    rol: Optional[str] = None
    dni: Optional[str] = None

    class Config:
        from_attributes = True
