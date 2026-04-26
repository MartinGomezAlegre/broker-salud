from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_common import require_admin
from app.schemas.catalogo import (
    CuponActualizar,
    CuponCrear,
    CuponEstado,
    PlanActualizar,
    PlanCrear,
    PlanOrden,
)
from app.services.catalogo import (
    actualizar_cupon,
    actualizar_orden_plan,
    actualizar_plan_catalogo,
    cambiar_estado_cupon,
    crear_cupon,
    crear_plan,
    eliminar_cupon,
    historial_catalogo,
    listar_cupones,
    listar_planes_admin,
    listar_servicios_catalogo,
    usos_cupon,
)

router = APIRouter(
    prefix="/admin/catalogo",
    tags=["catalogo"],
)

cupones_alias_router = APIRouter(
    prefix="/admin",
    tags=["catalogo"],
)


@router.get("/planes")
def listar_planes_admin_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_planes_admin(db)


@router.get("/services")
def listar_servicios_catalogo_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_servicios_catalogo(db)


@router.post("/planes")
def crear_plan_route(
    datos: PlanCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_plan(db, datos)


@router.put("/planes/{plan_id}")
def actualizar_plan_catalogo_route(
    plan_id: int,
    datos: PlanActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_plan_catalogo(db, plan_id, datos)


@router.put("/planes/{plan_id}/orden")
def actualizar_orden_plan_route(
    plan_id: int,
    datos: PlanOrden,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_orden_plan(db, plan_id, datos)


@router.get("/historial")
def historial_catalogo_route(
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return historial_catalogo(db, limit)


@router.get("/cupones")
def listar_cupones_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_cupones(db)


@router.post("/cupones")
def crear_cupon_route(
    datos: CuponCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_cupon(db, datos)


@router.put("/cupones/{cupon_id}")
def actualizar_cupon_route(
    cupon_id: int,
    datos: CuponActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_cupon(db, cupon_id, datos)


@router.put("/cupones/{cupon_id}/estado")
def cambiar_estado_cupon_route(
    cupon_id: int,
    datos: CuponEstado,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return cambiar_estado_cupon(db, cupon_id, datos)


@router.delete("/cupones/{cupon_id}")
def eliminar_cupon_route(
    cupon_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return eliminar_cupon(db, cupon_id)


@router.get("/cupones/{cupon_id}/usos")
def usos_cupon_route(
    cupon_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return usos_cupon(db, cupon_id)


@cupones_alias_router.get("/cupones")
def listar_cupones_alias_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_cupones(db)
