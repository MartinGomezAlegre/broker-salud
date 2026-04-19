from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.services.invitations import accept_account_invitation, get_account_invitation

router = APIRouter(prefix="/auth/invitaciones", tags=["invitaciones"])


class ActivarInvitacionData(BaseModel):
    token: str
    nueva_contrasenia: str


@router.get("/{token}")
@limiter.limit("30/hour")
def obtener_invitacion_route(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    try:
        return get_account_invitation(db, token)
    except HTTPException:
        raise


@router.post("/activar")
@limiter.limit("10/hour")
def activar_invitacion_route(
    request: Request,
    datos: ActivarInvitacionData,
    db: Session = Depends(get_db),
):
    return accept_account_invitation(db, datos.token, datos.nueva_contrasenia)
