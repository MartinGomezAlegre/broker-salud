from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_common import require_roles
from app.schemas.empresas import CambiarEstadoEmpleado, EmpleadoActualizar, EmpleadoCrear
from app.services.audit import log_audit_event
from app.services.empresas.companies import detalle_empresa
from app.services.empresas.employees import (
    actualizar_empleado,
    agregar_empleado,
    agregar_empleados_bulk_xlsx,
    analizar_empleados_bulk_xlsx,
    cambiar_estado_empleado,
    eliminar_empleado,
    listar_empleados,
)
from app.services.empresas.exports import exportar_empleados, exportar_plantilla_empleados_bulk

router = APIRouter(
    prefix="/empresa-admin",
    tags=["empresa_admin"],
)


def require_empresa_admin_context(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_roles("empresa_admin")),
):
    empresa = db.execute(
        text("SELECT id FROM empresas WHERE admin_user_id = :usuario_id"),
        {"usuario_id": usuario_id},
    ).fetchone()
    if not empresa:
        raise HTTPException(status_code=403, detail="Tu cuenta no esta vinculada a ninguna empresa.")
    return {"usuario_id": usuario_id, "empresa_id": empresa.id}


@router.get("/empresa")
def mi_empresa_route(
    request: Request,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    resultado = detalle_empresa(db, ctx["empresa_id"])
    resultado.pop("auditoria", None)
    log_audit_event(
        db,
        actor_user_id=ctx["usuario_id"],
        action="read_own_company_detail",
        entity_type="empresa",
        entity_id=ctx["empresa_id"],
        request=request,
    )
    return resultado


@router.get("/empleados")
def listar_mis_empleados_route(
    request: Request,
    activo: bool | None = Query(None),
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    resultado = listar_empleados(db, ctx["empresa_id"], activo)
    log_audit_event(
        db,
        actor_user_id=ctx["usuario_id"],
        action="read_own_company_employees",
        entity_type="empresa_empleados",
        entity_id=ctx["empresa_id"],
        request=request,
        metadata={"activo": activo, "count": len(resultado)},
    )
    return resultado


@router.post("/empleados")
def agregar_mi_empleado_route(
    datos: EmpleadoCrear,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    return agregar_empleado(db, ctx["empresa_id"], datos)


@router.put("/empleados/{empleado_id}")
def actualizar_mi_empleado_route(
    empleado_id: int,
    datos: EmpleadoActualizar,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    return actualizar_empleado(db, ctx["empresa_id"], empleado_id, datos)


@router.put("/empleados/{empleado_id}/estado")
def cambiar_estado_mi_empleado_route(
    empleado_id: int,
    datos: CambiarEstadoEmpleado,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    return cambiar_estado_empleado(db, ctx["empresa_id"], empleado_id, datos)


@router.delete("/empleados/{empleado_id}")
def eliminar_mi_empleado_route(
    empleado_id: int,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    return eliminar_empleado(db, ctx["empresa_id"], empleado_id)


@router.post("/empleados/bulk/dry-run")
async def analizar_mis_empleados_bulk_route(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    return analizar_empleados_bulk_xlsx(db, ctx["empresa_id"], await archivo.read())


@router.post("/empleados/bulk/upload")
async def agregar_mis_empleados_bulk_xlsx_route(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    return agregar_empleados_bulk_xlsx(db, ctx["empresa_id"], await archivo.read())


@router.get("/empleados/plantilla")
def exportar_mi_plantilla_empleados_route(
    _: dict = Depends(require_empresa_admin_context),
):
    return exportar_plantilla_empleados_bulk()


@router.get("/exportar-empleados")
def exportar_mis_empleados_route(
    request: Request,
    db: Session = Depends(get_db),
    ctx: dict = Depends(require_empresa_admin_context),
):
    response = exportar_empleados(db, ctx["empresa_id"])
    log_audit_event(
        db,
        actor_user_id=ctx["usuario_id"],
        action="export_own_company_employees_excel",
        entity_type="empresa_empleados",
        entity_id=ctx["empresa_id"],
        request=request,
    )
    return response
