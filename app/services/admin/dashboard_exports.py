from datetime import date
import io
import logging

import openpyxl
from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def exportar_excel(db: Session):
    try:
        rows = db.execute(text("""
            SELECT u.nombre, u.apellido, u.email, u.telefono, u.dni,
                   u.fecha_nacimiento, p.nombre AS plan_nombre,
                   s.estado, s.fecha_inicio
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE DATE(s.created_at) = CURRENT_DATE
            ORDER BY s.created_at DESC
        """)).fetchall()

        if not rows:
            rows = db.execute(text("""
                SELECT u.nombre, u.apellido, u.email, u.telefono, u.dni,
                       u.fecha_nacimiento, p.nombre AS plan_nombre,
                       s.estado, s.fecha_inicio
                FROM suscripciones s
                JOIN usuarios u ON u.id = s.usuario_id
                JOIN planes p ON p.id = s.plan_id
                ORDER BY s.created_at DESC
            """)).fetchall()

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Suscriptores"
        sheet.append([
            "Nombre",
            "Apellido",
            "Email",
            "Telefono",
            "DNI",
            "Fecha Nacimiento",
            "Plan",
            "Estado",
            "Fecha Suscripcion",
        ])

        for row in rows:
            sheet.append([
                row.nombre,
                row.apellido,
                row.email,
                row.telefono,
                row.dni if row.dni is not None else "",
                row.fecha_nacimiento.isoformat() if row.fecha_nacimiento else "",
                row.plan_nombre,
                row.estado,
                row.fecha_inicio.isoformat() if row.fecha_inicio else "",
            ])

        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        fecha_hoy = date.today().isoformat()

        return Response(
            content=buffer.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=suscriptores_{fecha_hoy}.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
