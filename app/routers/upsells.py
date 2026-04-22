from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.routers.admin_common import require_admin_panel
from app.schemas.upsells import UpsellSeguroActualizar, UpsellSeguroCrear
from app.services.upsells import (
    actualizar_upsell_seguro,
    crear_upsell_seguro,
    listar_upsells_seguro,
    mi_upsell_seguro,
)

router = APIRouter(prefix="/upsells", tags=["upsells"])
admin_router = APIRouter(prefix="/admin/upsells", tags=["upsells-admin"])


@router.get("/seguro/mio")
def mi_upsell_seguro_route(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return mi_upsell_seguro(db, usuario_id)


@router.post("/seguro")
def crear_upsell_seguro_route(
    datos: UpsellSeguroCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return crear_upsell_seguro(db, usuario_id, datos)


@admin_router.get("/seguro")
def listar_upsells_seguro_route(
    estado: str | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin_panel),
):
    return listar_upsells_seguro(db, estado)


@admin_router.put("/seguro/{upsell_id}")
def actualizar_upsell_seguro_route(
    upsell_id: int,
    datos: UpsellSeguroActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin_panel),
):
    return actualizar_upsell_seguro(db, upsell_id, datos)
