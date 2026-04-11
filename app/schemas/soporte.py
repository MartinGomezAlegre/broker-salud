from typing import Optional

from pydantic import BaseModel


class TicketCrear(BaseModel):
    asunto: str
    mensaje: str


class TicketResponder(BaseModel):
    respuesta: str
    estado: str = "respondido"
    prioridad: Optional[str] = None


class TicketEstado(BaseModel):
    estado: str
