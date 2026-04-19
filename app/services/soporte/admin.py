import logging
from typing import Optional

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.soporte import TicketEstado, TicketResponder
from app.services.email import dispatch_email, enviar_email_ticket_respondido
from app.services.soporte.common import (
    ESTADOS_TICKET,
    columna_mensaje_ticket,
    obtener_columnas_tickets,
    select_mensaje_ticket,
    select_texto_opcional,
    select_timestamp_opcional,
)

logger = logging.getLogger(__name__)


def listar_tickets_admin_service(db: Session, estado: Optional[str], prioridad: Optional[str]):
    try:
        columnas = obtener_columnas_tickets(db)
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
                SELECT t.id, t.asunto,
                       {select_mensaje_ticket(columnas)},
                       {select_texto_opcional(columnas, 'respuesta')},
                       {select_timestamp_opcional(columnas, 'respondido_en')},
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
        columnas = obtener_columnas_tickets(db)
        ticket = db.execute(
            text(
                """
                SELECT
                    t.id,
                    t.asunto,
                    {mensaje_select},
                    CASE
                        WHEN t.estado IS NULL OR t.estado = '' OR t.estado = 'nuevo' THEN 'abierto'
                        ELSE t.estado
                    END AS estado,
                    COALESCE(t.prioridad, 'normal') AS prioridad,
                    {respuesta_select},
                    {respondido_en_select},
                    t.created_at,
                    u.nombre,
                    u.apellido,
                    u.email,
                    u.telefono,
                    u.dni
                FROM tickets_soporte t
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE t.id = :id
                """
                .format(
                    mensaje_select=select_mensaje_ticket(columnas),
                    respuesta_select=select_texto_opcional(columnas, "respuesta"),
                    respondido_en_select=select_timestamp_opcional(columnas, "respondido_en"),
                )
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


def responder_ticket_service(
    db: Session,
    ticket_id: int,
    admin_id: int,
    datos: TicketResponder,
    background_tasks: BackgroundTasks | None = None,
):
    try:
        columnas = obtener_columnas_tickets(db)
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

        set_clauses = ["estado = :estado"]
        params: dict = {"id": ticket_id, "estado": datos.estado}

        if "respuesta" in columnas:
            set_clauses.insert(0, "respuesta = :respuesta")
            params["respuesta"] = datos.respuesta
        if "admin_id" in columnas:
            set_clauses.append("admin_id = :admin_id")
            params["admin_id"] = admin_id
        if "respondido_en" in columnas:
            set_clauses.append("respondido_en = NOW()")
        if "updated_at" in columnas:
            set_clauses.append("updated_at = NOW()")
        if datos.prioridad and "prioridad" in columnas:
            set_clauses.append("prioridad = :prioridad")
            params["prioridad"] = datos.prioridad

        db.execute(
            text(
                """
                UPDATE tickets_soporte
                SET {set_clauses}
                WHERE id = :id
                """
                .format(set_clauses=", ".join(set_clauses))
            ),
            params,
        )
        db.commit()

        dispatch_email(
            background_tasks,
            enviar_email_ticket_respondido,
            ticket.email,
            ticket.nombre,
            ticket.id,
            ticket.asunto,
            datos.respuesta,
        )

        actualizado = db.execute(
            text(
                """
                SELECT
                    id,
                    asunto,
                    {mensaje_select},
                    CASE
                        WHEN estado IS NULL OR estado = '' OR estado = 'nuevo' THEN 'abierto'
                        ELSE estado
                    END AS estado,
                    COALESCE(prioridad, 'normal') AS prioridad,
                    {respuesta_select},
                    {respondido_en_select}
                FROM tickets_soporte
                WHERE id = :id
                """.format(
                    mensaje_select=select_mensaje_ticket(columnas, alias="tickets_soporte"),
                    respuesta_select=select_texto_opcional(columnas, "respuesta", alias="tickets_soporte"),
                    respondido_en_select=select_timestamp_opcional(columnas, "respondido_en", alias="tickets_soporte"),
                )
            ),
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
        columnas = obtener_columnas_tickets(db)
        ticket = db.execute(
            text("SELECT id FROM tickets_soporte WHERE id = :id"),
            {"id": ticket_id},
        ).fetchone()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        set_clauses = ["estado = :estado"]
        if "updated_at" in columnas:
            set_clauses.append("updated_at = NOW()")
        db.execute(
            text("UPDATE tickets_soporte SET {set_clauses} WHERE id = :id".format(set_clauses=", ".join(set_clauses))),
            {"estado": datos.estado, "id": ticket_id},
        )
        db.commit()

        return {"id": ticket_id, "estado": datos.estado}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en cambiar_estado_ticket: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
