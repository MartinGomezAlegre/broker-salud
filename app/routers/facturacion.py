from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_common import require_admin
from app.schemas.facturacion import MarcarExportados, PagoManual
from app.services.facturacion import (
    exportar_mediquo,
    historial_exportaciones,
    listar_facturas,
    listar_pagos,
    marcar_exportados,
    pago_manual,
    resumen_facturacion,
)

router = APIRouter(
    prefix="/admin/facturacion",
    tags=["facturacion"],
)


@router.get("/pagos")
def listar_pagos_route(
    estado: str | None = Query(None),
    pasarela: str | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_pagos(db, estado, pasarela, fecha_desde, fecha_hasta)


@router.get("/resumen")
def resumen_facturacion_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return resumen_facturacion(db)


@router.get("/facturas")
def listar_facturas_route(
    tipo: str | None = Query(None),
    mes: str | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_facturas(db, tipo, mes)


@router.post("/pagos/manual")
def pago_manual_route(
    datos: PagoManual,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return pago_manual(db, datos)


@router.get("/exportar-mediquo")
def exportar_mediquo_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return exportar_mediquo(db)


@router.post("/marcar-exportados")
def marcar_exportados_route(
    datos: MarcarExportados,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return marcar_exportados(db, datos)


@router.get("/historial-exportaciones")
def historial_exportaciones_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return historial_exportaciones(db)
