from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_common import require_admin, require_roles
from app.schemas.comercial import (
    BrokerActualizar,
    BrokerCrear,
    BrokerPortalSellerActualizar,
    BrokerPortalSellerCrear,
    BrokerSellerActualizar,
    BrokerSellerCrear,
    DirectSellerActualizar,
    DirectSellerCrear,
    LiquidacionCrear,
)
from app.services.comercial.broker_team import (
    actualizar_broker_seller_desde_broker,
    crear_broker_seller_desde_broker,
    listar_mi_equipo_broker,
)
from app.services.comercial.admin import (
    actualizar_broker,
    actualizar_broker_seller,
    actualizar_direct_seller,
    crear_broker,
    crear_broker_seller,
    crear_direct_seller,
    crear_liquidacion,
    listar_broker_sellers,
    listar_brokers,
    listar_direct_sellers,
    listar_liquidaciones,
    listar_usuarios_comerciales,
    listar_ventas_referidas,
    resumen_comercial,
)
from app.services.comercial.portal import dashboard_comercial

router = APIRouter(prefix="/comercial", tags=["comercial"])
admin_router = APIRouter(prefix="/admin/comercial", tags=["admin-comercial"])


@router.get("/dashboard")
def dashboard_comercial_route(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_roles("broker", "direct_seller", "broker_seller")),
):
    return dashboard_comercial(db, usuario_id)


@router.get("/broker-sellers")
def listar_mi_equipo_broker_route(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_roles("broker")),
):
    return listar_mi_equipo_broker(db, usuario_id)


@router.post("/broker-sellers")
def crear_broker_seller_desde_broker_route(
    datos: BrokerPortalSellerCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_roles("broker")),
):
    return crear_broker_seller_desde_broker(
        db,
        usuario_id,
        nombre=datos.nombre,
        email=datos.email,
        contrasenia=datos.contrasenia,
        referral_code=datos.referral_code,
        estado=datos.estado,
    )


@router.put("/broker-sellers/{seller_id}")
def actualizar_broker_seller_desde_broker_route(
    seller_id: int,
    datos: BrokerPortalSellerActualizar,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_roles("broker")),
):
    return actualizar_broker_seller_desde_broker(
        db,
        usuario_id,
        seller_id,
        nombre=datos.nombre,
        email=datos.email,
        nueva_contrasenia=datos.nueva_contrasenia,
        referral_code=datos.referral_code,
        estado=datos.estado,
    )


@admin_router.get("/resumen")
def resumen_comercial_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return resumen_comercial(db)


@admin_router.get("/usuarios")
def listar_usuarios_comerciales_route(
    buscar: str | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_usuarios_comerciales(db, buscar)


@admin_router.get("/brokers")
def listar_brokers_route(
    estado: str | None = Query(None),
    buscar: str | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_brokers(db, estado, buscar)


@admin_router.post("/brokers")
def crear_broker_route(
    datos: BrokerCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_broker(db, datos)


@admin_router.put("/brokers/{broker_id}")
def actualizar_broker_route(
    broker_id: int,
    datos: BrokerActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_broker(db, broker_id, datos)


@admin_router.get("/broker-sellers")
def listar_broker_sellers_route(
    broker_id: int | None = Query(None),
    estado: str | None = Query(None),
    buscar: str | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_broker_sellers(db, broker_id, estado, buscar)


@admin_router.post("/broker-sellers")
def crear_broker_seller_route(
    datos: BrokerSellerCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_broker_seller(db, datos)


@admin_router.put("/broker-sellers/{seller_id}")
def actualizar_broker_seller_route(
    seller_id: int,
    datos: BrokerSellerActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_broker_seller(db, seller_id, datos)


@admin_router.get("/direct-sellers")
def listar_direct_sellers_route(
    estado: str | None = Query(None),
    buscar: str | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_direct_sellers(db, estado, buscar)


@admin_router.post("/direct-sellers")
def crear_direct_seller_route(
    datos: DirectSellerCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_direct_seller(db, datos)


@admin_router.put("/direct-sellers/{seller_id}")
def actualizar_direct_seller_route(
    seller_id: int,
    datos: DirectSellerActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_direct_seller(db, seller_id, datos)


@admin_router.get("/ventas")
def listar_ventas_route(
    canal: str | None = Query(None),
    estado: str | None = Query(None),
    buscar: str | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_ventas_referidas(db, canal, estado, buscar)


@admin_router.get("/liquidaciones")
def listar_liquidaciones_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_liquidaciones(db)


@admin_router.post("/liquidaciones")
def crear_liquidacion_route(
    datos: LiquidacionCrear,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    return crear_liquidacion(db, datos, admin_id)
