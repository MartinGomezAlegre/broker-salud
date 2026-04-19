from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.security.passwords import validate_password_strength
from app.security.validators import normalize_cuit, normalize_dni, normalize_phone


class UsuarioCrear(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    telefono: str
    fecha_nacimiento: date
    contrasenia: str
    dni: Optional[str] = None
    cuit: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    codigo_postal: Optional[str] = None
    provincia: Optional[str] = None
    pais: Optional[str] = None

    @field_validator("contrasenia")
    @classmethod
    def validar_contrasenia(cls, value: str):
        return validate_password_strength(value)

    @field_validator("nombre", "apellido")
    @classmethod
    def validar_nombre(cls, value: str):
        if len(value.strip()) < 2:
            raise ValueError("Debe tener al menos 2 caracteres")
        return value.strip()

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, value: str):
        telefono = normalize_phone(value)
        if telefono is None:
            raise ValueError("Ingresa un telefono valido")
        return telefono

    @field_validator("dni")
    @classmethod
    def validar_dni(cls, value: Optional[str]):
        return normalize_dni(value)

    @field_validator("cuit")
    @classmethod
    def validar_cuit(cls, value: Optional[str]):
        return normalize_cuit(value)

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, value: Optional[str]):
        if value is None or not value.strip():
            return None
        if len(value.strip()) < 6:
            raise ValueError("Ingresa una direccion valida")
        return value.strip()

    @field_validator("localidad", "provincia", "pais")
    @classmethod
    def validar_ubicacion(cls, value: Optional[str]):
        if value is None or not value.strip():
            return None
        if len(value.strip()) < 2:
            raise ValueError("Completa este dato correctamente")
        return value.strip()

    @field_validator("codigo_postal")
    @classmethod
    def validar_codigo_postal(cls, value: Optional[str]):
        if value is None or not value.strip():
            return None
        if len(value.strip()) < 3:
            raise ValueError("Ingresa un codigo postal valido")
        return value.strip()


class UsuarioRespuesta(BaseModel):
    id: int
    nombre: str
    apellido: str
    email: str
    rol: Optional[str] = None

    class Config:
        from_attributes = True
