from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_common import require_admin
from app.schemas.admin import ActualizarPlan, CambiarEstadoSuscripcion, CambiarEstadoUsuario
from app.services.audit import log_audit_event
from app.services.admin.dashboard import dashboard, exportar_excel, metricas_grafico, obtener_alertas
from app.services.admin.jobs import enviar_recordatorios, procesar_vencimientos
from app.services.admin.reports import metricas_embudo, metricas_retencion, reporte_mensual
from app.services.admin.subscriptions import actualizar_plan, cambiar_estado_suscripcion, listar_suscripciones
from app.services.admin.users import cambiar_estado_usuario, detalle_usuario, listar_usuarios

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.get("/dashboard")
def dashboard_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return dashboard(db)


@router.get("/metricas-grafico")
def metricas_grafico_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return metricas_grafico(db)


@router.get("/usuarios")
def listar_usuarios_route(
    request: Request,
    buscar: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    resultado = listar_usuarios(db, buscar, limit, offset)
    log_audit_event(
        db,
        actor_user_id=admin_id,
        action="read_user_list",
        entity_type="usuarios",
        entity_id="collection",
        request=request,
        metadata={"buscar": buscar, "limit": limit, "offset": offset, "count": len(resultado)},
    )
    return resultado


@router.get("/usuarios/{target_usuario_id}")
def detalle_usuario_route(
    request: Request,
    target_usuario_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    resultado = detalle_usuario(db, target_usuario_id)
    log_audit_event(
        db,
        actor_user_id=admin_id,
        action="read_user_detail",
        entity_type="usuario",
        entity_id=target_usuario_id,
        request=request,
        metadata={"includes_beneficiarios": bool(resultado.get("beneficiarios"))},
    )
    return resultado


@router.get("/suscripciones")
def listar_suscripciones_route(
    estado: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return listar_suscripciones(db, estado, limit, offset)


@router.get("/exportar-excel")
def exportar_excel_route(
    request: Request,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    response = exportar_excel(db)
    log_audit_event(
        db,
        actor_user_id=admin_id,
        action="export_subscriptions_excel",
        entity_type="suscripciones",
        entity_id="excel",
        request=request,
    )
    return response


@router.put("/planes/{plan_id}")
def actualizar_plan_route(
    plan_id: int,
    datos: ActualizarPlan,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return actualizar_plan(db, plan_id, datos)


@router.get("/alertas")
def obtener_alertas_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return obtener_alertas(db)


@router.put("/usuarios/{usuario_id}/estado")
def cambiar_estado_usuario_route(
    usuario_id: int,
    datos: CambiarEstadoUsuario,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return cambiar_estado_usuario(db, usuario_id, datos)


@router.put("/suscripciones/{suscripcion_id}/estado")
def cambiar_estado_suscripcion_route(
    suscripcion_id: int,
    datos: CambiarEstadoSuscripcion,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return cambiar_estado_suscripcion(db, suscripcion_id, datos, background_tasks=background_tasks)


@router.get("/metricas-retencion")
def metricas_retencion_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return metricas_retencion(db)


@router.get("/metricas-embudo")
def metricas_embudo_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return metricas_embudo(db)


@router.get("/reporte-mensual")
def reporte_mensual_route(
    mes: str | None = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return reporte_mensual(db, mes)


@router.post("/procesar-vencimientos")
def procesar_vencimientos_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return procesar_vencimientos(db)


@router.post("/enviar-recordatorios")
def enviar_recordatorios_route(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    return enviar_recordatorios(db)
