from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.limiter import limiter
from app.schemas.soporte import TicketCrear, TicketEstado, TicketResponder
from app.services.audit import log_audit_event
from app.services.soporte import (
    cambiar_estado_ticket_service,
    crear_ticket_service,
    listar_tickets_admin_service,
    mis_tickets_service,
    obtener_ticket_admin_service,
    require_admin_dep,
    responder_ticket_service,
)

router = APIRouter(prefix="/soporte", tags=["soporte"])
admin_router = APIRouter(prefix="/admin/soporte", tags=["admin-soporte"])


@router.post("/tickets")
@limiter.limit("10/hour")
def crear_ticket(
    request: Request,
    datos: TicketCrear,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return crear_ticket_service(
        db=db,
        usuario_id=usuario_id,
        datos=datos,
        background_tasks=background_tasks,
    )


@router.get("/mis-tickets")
def mis_tickets(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return mis_tickets_service(db=db, usuario_id=usuario_id)


@admin_router.get("/tickets")
def listar_tickets_admin(
    request: Request,
    estado: Optional[str] = Query(None),
    prioridad: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin_dep),
):
    resultado = listar_tickets_admin_service(db=db, estado=estado, prioridad=prioridad)
    log_audit_event(
        db,
        actor_user_id=admin_id,
        action="read_support_ticket_list",
        entity_type="tickets_soporte",
        entity_id="collection",
        request=request,
        metadata={"estado": estado, "prioridad": prioridad, "count": len(resultado)},
    )
    return resultado


@admin_router.get("/tickets/{ticket_id}")
def obtener_ticket_admin(
    request: Request,
    ticket_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin_dep),
):
    resultado = obtener_ticket_admin_service(db=db, ticket_id=ticket_id)
    log_audit_event(
        db,
        actor_user_id=admin_id,
        action="read_support_ticket_detail",
        entity_type="ticket_soporte",
        entity_id=ticket_id,
        request=request,
        metadata={"includes_dni": bool(resultado.get("usuario", {}).get("dni"))},
    )
    return resultado


@admin_router.put("/tickets/{ticket_id}/responder")
def responder_ticket(
    ticket_id: int,
    datos: TicketResponder,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin_dep),
):
    return responder_ticket_service(
        db=db,
        ticket_id=ticket_id,
        admin_id=admin_id,
        datos=datos,
        background_tasks=background_tasks,
    )


@admin_router.put("/tickets/{ticket_id}/estado")
def cambiar_estado_ticket(
    ticket_id: int,
    datos: TicketEstado,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin_dep),
):
    return cambiar_estado_ticket_service(db=db, ticket_id=ticket_id, datos=datos)
