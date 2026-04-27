from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.routers.admin_common import require_admin
from app.schemas.catalogo import (
    FarmaciaActualizar,
    FarmaciaCrear,
    CuponActualizar,
    CuponCrear,
    CuponEstado,
    MedicamentoActualizar,
    MedicamentoCrear,
    PlanActualizar,
    PlanCrear,
    PlanOrden,
)
from app.services.catalogo import (
    actualizar_farmacia,
    actualizar_medicamento,
    actualizar_cupon,
    actualizar_orden_plan,
    actualizar_plan_catalogo,
    cambiar_estado_cupon,
    crear_farmacia,
    crear_medicamento,
    crear_cupon,
    crear_plan,
    eliminar_cupon,
    historial_catalogo,
    listar_farmacias_admin,
    listar_farmacias_cliente,
    listar_cupones,
    listar_medicamentos_admin,
    listar_medicamentos_cliente,
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
cliente_catalogo_router = APIRouter(
    prefix="/catalogo",
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


@router.get("/medicamentos")
def listar_medicamentos_admin_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_medicamentos_admin(db)


@router.post("/medicamentos")
def crear_medicamento_route(
    datos: MedicamentoCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_medicamento(db, datos)


@router.put("/medicamentos/{medicamento_id}")
def actualizar_medicamento_route(
    medicamento_id: int,
    datos: MedicamentoActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_medicamento(db, medicamento_id, datos)


@router.get("/farmacias")
def listar_farmacias_admin_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_farmacias_admin(db)


@router.post("/farmacias")
def crear_farmacia_route(
    datos: FarmaciaCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_farmacia(db, datos)


@router.put("/farmacias/{farmacia_id}")
def actualizar_farmacia_route(
    farmacia_id: int,
    datos: FarmaciaActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_farmacia(db, farmacia_id, datos)


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


@cliente_catalogo_router.get("/medicamentos")
def listar_medicamentos_cliente_route(
    q: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
    _: int = Depends(get_current_user),
):
    return listar_medicamentos_cliente(db, q=q, limit=limit)


@cliente_catalogo_router.get("/farmacias")
def listar_farmacias_cliente_route(
    q: str | None = Query(default=None, min_length=1, max_length=80),
    localidad: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
    _: int = Depends(get_current_user),
):
    return listar_farmacias_cliente(db, q=q, localidad=localidad, limit=limit)
