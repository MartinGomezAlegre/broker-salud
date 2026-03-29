import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/soporte",
    tags=["soporte"]
)

admin_router = APIRouter(
    prefix="/admin/soporte",
    tags=["admin-soporte"]
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class TicketCrear(BaseModel):
    asunto: str
    mensaje: str


class TicketResponder(BaseModel):
    respuesta: str
    estado: str = "respondido"
    prioridad: Optional[str] = None


class TicketEstado(BaseModel):
    estado: str


ESTADOS_TICKET = {"abierto", "respondido", "cerrado"}


# ── require_admin local (definido antes de usarlo como default param) ──────────

def _require_admin_dep(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    from app.routers.admin import require_admin
    return require_admin(db=db, usuario_id=usuario_id)


# ── Endpoints de usuario ───────────────────────────────────────────────────────

@router.post("/tickets")
def crear_ticket(
    datos: TicketCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        if len(datos.asunto.strip()) < 5:
            raise HTTPException(status_code=400, detail="El asunto debe tener al menos 5 caracteres")
        if len(datos.asunto) > 200:
            raise HTTPException(status_code=400, detail="El asunto no puede superar los 200 caracteres")
        if len(datos.mensaje.strip()) < 10:
            raise HTTPException(status_code=400, detail="El mensaje debe tener al menos 10 caracteres")
        if len(datos.mensaje) > 2000:
            raise HTTPException(status_code=400, detail="El mensaje no puede superar los 2000 caracteres")

        ticket = db.execute(
            text("""
                INSERT INTO tickets_soporte (usuario_id, asunto, mensaje)
                VALUES (:usuario_id, :asunto, :mensaje)
                RETURNING id, asunto, mensaje, estado, prioridad, created_at
            """),
            {"usuario_id": usuario_id, "asunto": datos.asunto.strip(), "mensaje": datos.mensaje.strip()}
        ).fetchone()
        db.commit()

        usuario = db.execute(
            text("SELECT nombre, email FROM usuarios WHERE id = :id"),
            {"id": usuario_id}
        ).fetchone()

        try:
            from app.services.email import enviar_email_ticket_recibido
            enviar_email_ticket_recibido(usuario.email, usuario.nombre, ticket.id, ticket.asunto)
        except Exception as e:
            logger.error("Error enviando email ticket recibido: %s", e)

        return {
            "id": ticket.id,
            "asunto": ticket.asunto,
            "mensaje": ticket.mensaje,
            "estado": ticket.estado,
            "prioridad": ticket.prioridad,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en crear_ticket: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/mis-tickets")
def mis_tickets(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        tickets = db.execute(
            text("""
                SELECT id, asunto, estado, prioridad, respuesta, created_at, respondido_en
                FROM tickets_soporte
                WHERE usuario_id = :usuario_id
                ORDER BY created_at DESC
            """),
            {"usuario_id": usuario_id}
        ).fetchall()

        return [
            {
                "id": t.id,
                "asunto": t.asunto,
                "estado": t.estado,
                "prioridad": t.prioridad,
                "respuesta": t.respuesta,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "respondido_en": t.respondido_en.isoformat() if t.respondido_en else None,
            }
            for t in tickets
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en mis_tickets: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ── Endpoints de admin ─────────────────────────────────────────────────────────

@admin_router.get("/tickets")
def listar_tickets_admin(
    estado: Optional[str] = Query(None),
    prioridad: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(_require_admin_dep)
):
    try:
        filtros = []
        params: dict = {}
        if estado:
            filtros.append("t.estado = :estado")
            params["estado"] = estado
        if prioridad:
            filtros.append("t.prioridad = :prioridad")
            params["prioridad"] = prioridad

        where = ("WHERE " + " AND ".join(filtros)) if filtros else ""

        tickets = db.execute(text(f"""
            SELECT t.id, t.asunto, t.mensaje, t.estado, t.prioridad, t.created_at,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email
            FROM tickets_soporte t
            JOIN usuarios u ON u.id = t.usuario_id
            {where}
            ORDER BY
                CASE t.prioridad WHEN 'alta' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END ASC,
                t.created_at ASC
        """), params).fetchall()

        return [
            {
                "id": t.id,
                "usuario_nombre": t.usuario_nombre,
                "usuario_email": t.usuario_email,
                "asunto": t.asunto,
                "mensaje": t.mensaje,
                "estado": t.estado,
                "prioridad": t.prioridad,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en listar_tickets_admin: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@admin_router.get("/tickets/{ticket_id}")
def obtener_ticket_admin(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(_require_admin_dep)
):
    try:
        ticket = db.execute(
            text("""
                SELECT t.*, u.nombre, u.apellido, u.email, u.telefono, u.dni
                FROM tickets_soporte t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE t.id = :id
            """),
            {"id": ticket_id}
        ).fetchone()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        return {
            "id": ticket.id,
            "asunto": ticket.asunto,
            "mensaje": ticket.mensaje,
            "estado": ticket.estado,
            "prioridad": ticket.prioridad,
            "respuesta": ticket.respuesta,
            "respondido_en": ticket.respondido_en.isoformat() if ticket.respondido_en else None,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "usuario": {
                "nombre": ticket.nombre,
                "apellido": ticket.apellido,
                "email": ticket.email,
                "telefono": ticket.telefono,
                "dni": ticket.dni,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en obtener_ticket_admin: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@admin_router.put("/tickets/{ticket_id}/responder")
def responder_ticket(
    ticket_id: int,
    datos: TicketResponder,
    db: Session = Depends(get_db),
    admin_id: int = Depends(_require_admin_dep)
):
    try:
        ticket = db.execute(
            text("""
                SELECT t.id, t.asunto, t.usuario_id,
                       u.email, u.nombre
                FROM tickets_soporte t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE t.id = :id
            """),
            {"id": ticket_id}
        ).fetchone()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        params: dict = {
            "id": ticket_id,
            "respuesta": datos.respuesta,
            "estado": datos.estado,
            "admin_id": admin_id,
        }
        prioridad_sql = ""
        if datos.prioridad:
            prioridad_sql = ", prioridad = :prioridad"
            params["prioridad"] = datos.prioridad

        db.execute(text(f"""
            UPDATE tickets_soporte
            SET respuesta = :respuesta,
                estado = :estado,
                admin_id = :admin_id,
                respondido_en = NOW(),
                updated_at = NOW()
                {prioridad_sql}
            WHERE id = :id
        """), params)
        db.commit()

        try:
            from app.services.email import enviar_email_ticket_respondido
            enviar_email_ticket_respondido(
                ticket.email, ticket.nombre, ticket.id,
                ticket.asunto, datos.respuesta
            )
        except Exception as e:
            logger.error("Error enviando email ticket respondido: %s", e)

        actualizado = db.execute(
            text("SELECT * FROM tickets_soporte WHERE id = :id"),
            {"id": ticket_id}
        ).fetchone()

        return {
            "id": actualizado.id,
            "asunto": actualizado.asunto,
            "respuesta": actualizado.respuesta,
            "estado": actualizado.estado,
            "prioridad": actualizado.prioridad,
            "respondido_en": actualizado.respondido_en.isoformat() if actualizado.respondido_en else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en responder_ticket: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@admin_router.put("/tickets/{ticket_id}/estado")
def cambiar_estado_ticket(
    ticket_id: int,
    datos: TicketEstado,
    db: Session = Depends(get_db),
    _: int = Depends(_require_admin_dep)
):
    try:
        if datos.estado not in ESTADOS_TICKET:
            raise HTTPException(
                status_code=400,
                detail=f"Estado inválido. Permitidos: {', '.join(ESTADOS_TICKET)}"
            )

        ticket = db.execute(
            text("SELECT id FROM tickets_soporte WHERE id = :id"),
            {"id": ticket_id}
        ).fetchone()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        db.execute(
            text("UPDATE tickets_soporte SET estado = :estado, updated_at = NOW() WHERE id = :id"),
            {"estado": datos.estado, "id": ticket_id}
        )
        db.commit()

        return {"id": ticket_id, "estado": datos.estado}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en cambiar_estado_ticket: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
