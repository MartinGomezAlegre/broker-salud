from typing import Optional

from pydantic import BaseModel


class CredencialVirtual(BaseModel):
    nombre_completo: str
    dni: Optional[str] = None
    numero_socio: str
    plan_nombre: str
    benefit_type: str
    discount_percentage: int
    qr_token: str
    qr_expires_at: str
    validation_url: str
    qr_image_data_url: str


class ValidacionBeneficio(BaseModel):
    valido: bool
    motivo: Optional[str] = None
    nombre_completo: Optional[str] = None
    numero_socio: Optional[str] = None
    plan_nombre: Optional[str] = None
    benefit_type: Optional[str] = None
    discount_percentage: Optional[int] = None
    checked_at: str
