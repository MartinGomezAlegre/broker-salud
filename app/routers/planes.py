import logging
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from app.database import get_db
from app.limiter import limiter
from app.schemas.planes import PlanRespuesta

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/planes",
    tags=["planes"]
)


@router.get("", response_model=List[PlanRespuesta])
@limiter.limit("60/minute")
def listar_planes(
    request: Request,
    tipo: Optional[str] = Query(None, description="'personal' o 'empresa'"),
    db: Session = Depends(get_db)
):
    if tipo == "personal":
        planes = db.execute(
            text("SELECT * FROM planes WHERE activo = true AND tipo IN ('personal', 'familiar')")
        ).fetchall()
    elif tipo == "empresa":
        planes = db.execute(
            text("SELECT * FROM planes WHERE activo = true AND tipo IN ('empresa', 'corporativo')")
        ).fetchall()
    else:
        planes = db.execute(
            text("SELECT * FROM planes WHERE activo = true")
        ).fetchall()

    return planes
