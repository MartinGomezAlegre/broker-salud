import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.soporte import TicketCrear
from app.services.soporte.common import (
    columna_mensaje_ticket,
    obtener_columnas_tickets,
    select_mensaje_ticket,
    select_texto_opcional,
    select_timestamp_opcional,
)

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
        columnas = obtener_columnas_tickets(db)
        columna_mensaje = columna_mensaje_ticket(columnas)
        if not columna_mensaje:
            raise HTTPException(status_code=500, detail="La tabla tickets_soporte no tiene una columna de mensaje compatible.")

        insert_columns = ["usuario_id", "asunto", columna_mensaje, "estado", "prioridad"]
        insert_values = [":usuario_id", ":asunto", ":mensaje", "'abierto'", "'normal'"]
        if "updated_at" in columnas:
            insert_columns.append("updated_at")
            insert_values.append("NOW()")

        ticket = db.execute(
            text(
                """
                INSERT INTO tickets_soporte ({insert_columns})
                VALUES ({insert_values})
                RETURNING
                    id,
                    asunto,
                    {mensaje_select},
                    CASE
                        WHEN estado IS NULL OR estado = '' OR estado = 'nuevo' THEN 'abierto'
                        ELSE estado
                    END AS estado,
                    COALESCE(prioridad, 'normal') AS prioridad,
                    created_at
                """
                .format(
                    insert_columns=", ".join(insert_columns),
                    insert_values=", ".join(insert_values),
                    mensaje_select=f"{columna_mensaje} AS mensaje",
                )
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
        columnas = obtener_columnas_tickets(db)
        tickets = db.execute(
            text(
                """
                SELECT id, asunto,
                       {mensaje_select},
                       CASE
                           WHEN estado IS NULL OR estado = '' OR estado = 'nuevo' THEN 'abierto'
                           ELSE estado
                       END AS estado,
                       COALESCE(prioridad, 'normal') AS prioridad,
                       {respuesta_select},
                       created_at,
                       {respondido_en_select}
                FROM tickets_soporte
                WHERE usuario_id = :usuario_id
                ORDER BY created_at DESC
                """
                .format(
                    mensaje_select=select_mensaje_ticket(columnas, alias="tickets_soporte"),
                    respuesta_select=select_texto_opcional(columnas, "respuesta", alias="tickets_soporte"),
                    respondido_en_select=select_timestamp_opcional(columnas, "respondido_en", alias="tickets_soporte"),
                )
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
