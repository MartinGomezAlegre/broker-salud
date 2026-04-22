from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.security.passwords import validate_password_strength
from app.security.validators import normalize_phone


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


class PersonalCrear(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    contrasenia: str
    rol: str
    telefono: Optional[str] = None
    area: Optional[str] = None
    cargo: Optional[str] = None
    responsabilidades: Optional[str] = None
    empresa_ids: list[int] = Field(default_factory=list)

    @field_validator("contrasenia")
    @classmethod
    def validar_contrasenia(cls, value: str):
        return validate_password_strength(value)

    @field_validator("nombre", "apellido", "area", "cargo")
    @classmethod
    def limpiar_texto(cls, value: Optional[str]):
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            return None
        return clean

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, value: Optional[str]):
        return normalize_phone(value)

    @field_validator("empresa_ids")
    @classmethod
    def validar_empresa_ids(cls, value: list[int]):
        limpias = sorted({empresa_id for empresa_id in value if isinstance(empresa_id, int) and empresa_id > 0})
        return limpias


class PersonalActualizar(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    rol: Optional[str] = None
    area: Optional[str] = None
    cargo: Optional[str] = None
    responsabilidades: Optional[str] = None
    nueva_contrasenia: Optional[str] = None
    empresa_ids: Optional[list[int]] = None

    @field_validator("nueva_contrasenia")
    @classmethod
    def validar_nueva_contrasenia(cls, value: Optional[str]):
        if value is None or not value.strip():
            return None
        return validate_password_strength(value)

    @field_validator("nombre", "apellido", "area", "cargo", "responsabilidades")
    @classmethod
    def limpiar_texto(cls, value: Optional[str]):
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, value: Optional[str]):
        return normalize_phone(value)

    @field_validator("empresa_ids")
    @classmethod
    def validar_empresa_ids(cls, value: Optional[list[int]]):
        if value is None:
            return None
        limpias = sorted({empresa_id for empresa_id in value if isinstance(empresa_id, int) and empresa_id > 0})
        return limpias
