import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.soporte import TicketCrear

logger = logging.getLogger(__name__)


def crear_ticket_service(db: Session, usuario_id: int, datos: TicketCrear):
    if len(datos.asunto.strip()) < 5:
        raise HTTPException(status_code=400, detail="El asunto debe tener al menos 5 caracteres")
    if len(datos.asunto) > 200:
        raise HTTPException(status_code=400, detail="El asunto no puede superar los 200 caracteres")
    if len(datos.mensaje.strip()) < 10:
        raise HTTPException(status_code=400, detail="El mensaje debe tener al menos 10 caracteres")
    if len(datos.mensaje) > 2000:
        raise HTTPException(status_code=400, detail="El mensaje no puede superar los 2000 caracteres")

    try:
        ticket = db.execute(
            text(
                """
                INSERT INTO tickets_soporte (usuario_id, asunto, mensaje, estado, prioridad, updated_at)
                VALUES (:usuario_id, :asunto, :mensaje, 'abierto', 'normal', NOW())
                RETURNING id, asunto, mensaje, estado, prioridad, created_at
                """
            ),
            {"usuario_id": usuario_id, "asunto": datos.asunto.strip(), "mensaje": datos.mensaje.strip()},
        ).fetchone()
        db.commit()

        usuario = db.execute(
            text("SELECT nombre, email FROM usuarios WHERE id = :id"),
            {"id": usuario_id},
        ).fetchone()

        try:
            from app.services.email import enviar_email_ticket_recibido

            enviar_email_ticket_recibido(usuario.email, usuario.nombre, ticket.id, ticket.asunto)
        except Exception as exc:
            logger.error("Error enviando email ticket recibido: %s", exc)

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
    except Exception as exc:
        logger.error("Error en crear_ticket: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def mis_tickets_service(db: Session, usuario_id: int):
    try:
        tickets = db.execute(
            text(
                """
                SELECT id, asunto,
                       CASE
                           WHEN estado IS NULL OR estado = '' OR estado = 'nuevo' THEN 'abierto'
                           ELSE estado
                       END AS estado,
                       COALESCE(prioridad, 'normal') AS prioridad,
                       respuesta, created_at, respondido_en
                FROM tickets_soporte
                WHERE usuario_id = :usuario_id
                ORDER BY created_at DESC
                """
            ),
            {"usuario_id": usuario_id},
        ).fetchall()

        return [
            {
                "id": ticket.id,
                "asunto": ticket.asunto,
                "estado": ticket.estado,
                "prioridad": ticket.prioridad,
                "respuesta": ticket.respuesta,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "respondido_en": ticket.respondido_en.isoformat() if ticket.respondido_en else None,
            }
            for ticket in tickets
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en mis_tickets: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
