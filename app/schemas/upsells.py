from typing import Optional

from pydantic import BaseModel


class UpsellSeguroCrear(BaseModel):
    acepta: bool = True


class UpsellSeguroActualizar(BaseModel):
    estado: str
    nota_admin: Optional[str] = None
