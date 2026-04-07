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
    cuit: str
    direccion: str
    localidad: str
    codigo_postal: str
    provincia: str
    pais: str

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

    @field_validator("cuit")
    @classmethod
    def validar_cuit(cls, v):
        if len(v.strip()) < 8:
            raise ValueError("Ingresá un CUIT o CUIL válido")
        return v.strip()

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, v):
        if len(v.strip()) < 6:
            raise ValueError("Ingresá una dirección válida")
        return v.strip()

    @field_validator("localidad", "provincia", "pais")
    @classmethod
    def validar_ubicacion(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Completá este dato correctamente")
        return v.strip()

    @field_validator("codigo_postal")
    @classmethod
    def validar_codigo_postal(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("Ingresá un código postal válido")
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
