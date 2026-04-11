from datetime import date
import io
import logging

import openpyxl
from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def exportar_empleados(db: Session, empresa_id: int):
    try:
        empresa = db.execute(
            text("SELECT razon_social FROM empresas WHERE id = :id"),
            {"id": empresa_id},
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        rows = db.execute(text("""
            SELECT nombre, apellido, dni, email, cargo, telefono,
                   activo, fecha_alta, fecha_baja
            FROM empleados_empresa
            WHERE empresa_id = :id
            ORDER BY fecha_alta DESC
        """), {"id": empresa_id}).fetchall()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Empleados"
        ws.append(["Nombre", "Apellido", "DNI", "Email", "Cargo", "Telefono", "Estado", "Fecha Alta", "Fecha Baja"])

        for row in rows:
            ws.append([
                row.nombre,
                row.apellido,
                row.dni or "",
                row.email,
                row.cargo or "",
                row.telefono or "",
                "Activo" if row.activo else "Inactivo",
                row.fecha_alta.isoformat() if row.fecha_alta else "",
                row.fecha_baja.isoformat() if row.fecha_baja else "",
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        razon = empresa.razon_social.replace(" ", "_")[:30]
        fecha = date.today().isoformat()
        return Response(
            content=buffer.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=empleados_{razon}_{fecha}.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def exportar_empresas(db: Session):
    try:
        rows = db.execute(text("""
            SELECT e.razon_social, e.cuit,
                   COUNT(em.id) FILTER (WHERE em.activo = true) AS empleados_activos,
                   p.nombre AS plan_nombre,
                   se.estado AS estado_suscripcion,
                   se.proximo_cobro,
                   se.precio_total
            FROM empresas e
            LEFT JOIN empleados_empresa em ON em.empresa_id = e.id
            LEFT JOIN suscripciones_empresariales se ON se.empresa_id = e.id
                AND se.estado NOT IN ('cancelada', 'vencida')
            LEFT JOIN planes p ON p.id = se.plan_id
            GROUP BY e.razon_social, e.cuit, p.nombre,
                     se.estado, se.proximo_cobro, se.precio_total
            ORDER BY e.razon_social
        """)).fetchall()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Empresas"
        ws.append(["Razón Social", "CUIT", "Empleados activos", "Plan", "Estado suscripción", "Próximo cobro", "Monto mensual"])

        for row in rows:
            ws.append([
                row.razon_social,
                row.cuit,
                row.empleados_activos or 0,
                row.plan_nombre or "",
                row.estado_suscripcion or "",
                row.proximo_cobro.isoformat() if row.proximo_cobro else "",
                float(row.precio_total) if row.precio_total else 0,
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        fecha = date.today().isoformat()
        return Response(
            content=buffer.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=empresas_{fecha}.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
