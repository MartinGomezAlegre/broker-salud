import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.soporte import TicketEstado, TicketResponder
from app.services.soporte.common import ESTADOS_TICKET

logger = logging.getLogger(__name__)


def listar_tickets_admin_service(db: Session, estado: Optional[str], prioridad: Optional[str]):
    try:
        filtros = []
        params: dict = {}

        if estado:
            if estado == "abierto":
                filtros.append("(t.estado = :estado OR t.estado = 'nuevo' OR t.estado IS NULL OR t.estado = '')")
            else:
                filtros.append("t.estado = :estado")
            params["estado"] = estado

        if prioridad:
            filtros.append("t.prioridad = :prioridad")
            params["prioridad"] = prioridad

        where = ("WHERE " + " AND ".join(filtros)) if filtros else ""

        tickets = db.execute(
            text(
                f"""
                SELECT t.id, t.asunto, t.mensaje, t.respuesta, t.respondido_en,
                       CASE
                           WHEN t.estado IS NULL OR t.estado = '' OR t.estado = 'nuevo' THEN 'abierto'
                           ELSE t.estado
                       END AS estado,
                       COALESCE(t.prioridad, 'normal') AS prioridad,
                       t.created_at,
                       u.nombre || ' ' || u.apellido AS usuario_nombre,
                       u.email AS usuario_email
                FROM tickets_soporte t
                JOIN usuarios u ON u.id = t.usuario_id
                {where}
                ORDER BY
                    CASE t.prioridad WHEN 'alta' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END ASC,
                    t.created_at ASC
                """
            ),
            params,
        ).fetchall()

        return [
            {
                "id": ticket.id,
                "usuario_nombre": ticket.usuario_nombre,
                "usuario_email": ticket.usuario_email,
                "asunto": ticket.asunto,
                "mensaje": ticket.mensaje,
                "estado": ticket.estado,
                "prioridad": ticket.prioridad,
                "respuesta": ticket.respuesta,
                "respondido_en": ticket.respondido_en.isoformat() if ticket.respondido_en else None,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            }
            for ticket in tickets
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_tickets_admin: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def obtener_ticket_admin_service(db: Session, ticket_id: int):
    try:
        ticket = db.execute(
            text(
                """
                SELECT t.*, u.nombre, u.apellido, u.email, u.telefono, u.dni
                FROM tickets_soporte t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE t.id = :id
                """
            ),
            {"id": ticket_id},
        ).fetchone()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        return {
            "id": ticket.id,
            "asunto": ticket.asunto,
            "mensaje": ticket.mensaje,
            "estado": "abierto" if ticket.estado in (None, "", "nuevo") else ticket.estado,
            "prioridad": ticket.prioridad or "normal",
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
    except Exception as exc:
        logger.error("Error en obtener_ticket_admin: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def responder_ticket_service(db: Session, ticket_id: int, admin_id: int, datos: TicketResponder):
    try:
        ticket = db.execute(
            text(
                """
                SELECT t.id, t.asunto, t.usuario_id,
                       u.email, u.nombre
                FROM tickets_soporte t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE t.id = :id
                """
            ),
            {"id": ticket_id},
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

        db.execute(
            text(
                f"""
                UPDATE tickets_soporte
                SET respuesta = :respuesta,
                    estado = :estado,
                    admin_id = :admin_id,
                    respondido_en = NOW(),
                    updated_at = NOW()
                    {prioridad_sql}
                WHERE id = :id
                """
            ),
            params,
        )
        db.commit()

        try:
            from app.services.email import enviar_email_ticket_respondido

            enviar_email_ticket_respondido(ticket.email, ticket.nombre, ticket.id, ticket.asunto, datos.respuesta)
        except Exception as exc:
            logger.error("Error enviando email ticket respondido: %s", exc)

        actualizado = db.execute(
            text("SELECT * FROM tickets_soporte WHERE id = :id"),
            {"id": ticket_id},
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
    except Exception as exc:
        logger.error("Error en responder_ticket: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def cambiar_estado_ticket_service(db: Session, ticket_id: int, datos: TicketEstado):
    if datos.estado not in ESTADOS_TICKET:
        raise HTTPException(
            status_code=400,
            detail=f"Estado invalido. Permitidos: {', '.join(ESTADOS_TICKET)}",
        )

    try:
        ticket = db.execute(
            text("SELECT id FROM tickets_soporte WHERE id = :id"),
            {"id": ticket_id},
        ).fetchone()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        db.execute(
            text("UPDATE tickets_soporte SET estado = :estado, updated_at = NOW() WHERE id = :id"),
            {"estado": datos.estado, "id": ticket_id},
        )
        db.commit()

        return {"id": ticket_id, "estado": datos.estado}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en cambiar_estado_ticket: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
