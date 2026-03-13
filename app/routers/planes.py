from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schemas.planes import PlanRespuesta
from typing import List

router = APIRouter(
    prefix="/planes",
    tags=["planes"]
)

@router.get("/", response_model=List[PlanRespuesta])
def listar_planes(db: Session = Depends(get_db)):
    planes = db.execute(
        text("SELECT * FROM planes WHERE activo = true")
    ).fetchall()

    return planes