import logging
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.limiter import limiter
from app.schemas.planes import PlanRespuesta
from app.services.catalogo import listar_planes_publicos

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/planes",
    tags=["planes"]
)


@router.get("", response_model=List[PlanRespuesta])
@limiter.limit("60/minute")
def listar_planes(
    request: Request,
    response: Response,
    tipo: Optional[str] = Query(None, description="'personal' o 'empresa'"),
    db: Session = Depends(get_db)
):
    return listar_planes_publicos(db, tipo)
