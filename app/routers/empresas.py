from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_common import require_admin
from app.schemas.empresas import (
    BulkEmpleados,
    CambiarEstadoEmpleado,
    CambiarEstadoEmpresa,
    CambiarEstadoSuscripcionEmpresarial,
    EmpleadoActualizar,
    EmpleadoCrear,
    EmpresaActualizar,
    EmpresaCrear,
    SuscripcionEmpresarialCrear,
)
from app.services.empresas.companies import (
    actualizar_empresa,
    cambiar_estado_empresa,
    crear_empresa,
    detalle_empresa,
    listar_empresas,
)
from app.services.empresas.employees import (
    actualizar_empleado,
    agregar_empleado,
    agregar_empleados_bulk,
    cambiar_estado_empleado,
    eliminar_empleado,
    listar_empleados,
)
from app.services.empresas.exports import exportar_empleados, exportar_empresas
from app.services.empresas.metrics import metricas_empresas
from app.services.empresas.subscriptions import (
    cambiar_estado_suscripcion_empresarial,
    crear_suscripcion_empresarial,
    ver_suscripcion_empresarial,
)

router = APIRouter(
    prefix="/admin/empresas",
    tags=["empresas"],
)


@router.get("")
def listar_empresas_route(
    activo: bool | None = Query(None),
    buscar: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_empresas(db, activo, buscar, limit, offset)


@router.post("")
def crear_empresa_route(
    datos: EmpresaCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_empresa(db, datos)


@router.get("/exportar-empresas")
def exportar_empresas_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return exportar_empresas(db)


@router.get("/metricas-empresas")
def metricas_empresas_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return metricas_empresas(db)


@router.get("/{empresa_id}")
def detalle_empresa_route(
    empresa_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return detalle_empresa(db, empresa_id)


@router.put("/{empresa_id}")
def actualizar_empresa_route(
    empresa_id: int,
    datos: EmpresaActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_empresa(db, empresa_id, datos)


@router.put("/{empresa_id}/estado")
def cambiar_estado_empresa_route(
    empresa_id: int,
    datos: CambiarEstadoEmpresa,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return cambiar_estado_empresa(db, empresa_id, datos)


@router.post("/{empresa_id}/suscripcion")
def crear_suscripcion_empresarial_route(
    empresa_id: int,
    datos: SuscripcionEmpresarialCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return crear_suscripcion_empresarial(db, empresa_id, datos)


@router.put("/{empresa_id}/suscripcion/estado")
def cambiar_estado_suscripcion_empresarial_route(
    empresa_id: int,
    datos: CambiarEstadoSuscripcionEmpresarial,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return cambiar_estado_suscripcion_empresarial(db, empresa_id, datos)


@router.get("/{empresa_id}/suscripcion")
def ver_suscripcion_empresarial_route(
    empresa_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return ver_suscripcion_empresarial(db, empresa_id)


@router.get("/{empresa_id}/empleados")
def listar_empleados_route(
    empresa_id: int,
    activo: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_empleados(db, empresa_id, activo)


@router.post("/{empresa_id}/empleados")
def agregar_empleado_route(
    empresa_id: int,
    datos: EmpleadoCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return agregar_empleado(db, empresa_id, datos)


@router.post("/{empresa_id}/empleados/bulk")
def agregar_empleados_bulk_route(
    empresa_id: int,
    datos: BulkEmpleados,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return agregar_empleados_bulk(db, empresa_id, datos)


@router.put("/{empresa_id}/empleados/{empleado_id}")
def actualizar_empleado_route(
    empresa_id: int,
    empleado_id: int,
    datos: EmpleadoActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_empleado(db, empresa_id, empleado_id, datos)


@router.put("/{empresa_id}/empleados/{empleado_id}/estado")
def cambiar_estado_empleado_route(
    empresa_id: int,
    empleado_id: int,
    datos: CambiarEstadoEmpleado,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return cambiar_estado_empleado(db, empresa_id, empleado_id, datos)


@router.delete("/{empresa_id}/empleados/{empleado_id}")
def eliminar_empleado_route(
    empresa_id: int,
    empleado_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return eliminar_empleado(db, empresa_id, empleado_id)


@router.get("/{empresa_id}/exportar-empleados")
def exportar_empleados_route(
    empresa_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return exportar_empleados(db, empresa_id)


@router.get("/{empresa_id}/exportar-excel")
def exportar_empleados_alias_route(
    empresa_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return exportar_empleados(db, empresa_id)
