from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.limiter import limiter
from app.schemas.credenciales import CredencialVirtual, ValidacionBeneficio
from app.services.credenciales import obtener_credencial_virtual, validar_beneficio_token

router = APIRouter(prefix="/credenciales", tags=["credenciales"])
public_router = APIRouter(prefix="/validaciones", tags=["validaciones"])


@router.get("/mia", response_model=CredencialVirtual)
def obtener_credencial_virtual_route(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return obtener_credencial_virtual(db, usuario_id)


@public_router.get("/beneficios/{token}", response_model=ValidacionBeneficio)
@limiter.limit("30/minute")
def validar_beneficio_token_route(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    return validar_beneficio_token(
        db=db,
        token=token,
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
