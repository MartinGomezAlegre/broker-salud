from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.routers.admin import require_admin
from datetime import date
import io
import openpyxl

router = APIRouter(
    prefix="/admin/facturacion",
    tags=["facturacion"]
)


class PagoManual(BaseModel):
    usuario_id: int
    plan_id: int
    monto: float
    metodo: str
    descripcion: Optional[str] = None


# ─── Pagos ────────────────────────────────────────────────────────────────────

@router.get("/pagos")
def listar_pagos(
    estado: Optional[str] = Query(None),
    pasarela: Optional[str] = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        condiciones = ["1=1"]
        params: dict = {}

        if estado:
            condiciones.append("p.estado = :estado")
            params["estado"] = estado
        if pasarela:
            condiciones.append("p.pasarela = :pasarela")
            params["pasarela"] = pasarela
        if fecha_desde:
            condiciones.append("p.created_at >= :fecha_desde")
            params["fecha_desde"] = fecha_desde
        if fecha_hasta:
            condiciones.append("p.created_at <= :fecha_hasta")
            params["fecha_hasta"] = fecha_hasta

        where = " AND ".join(condiciones)

        rows = db.execute(text(f"""
            SELECT p.id,
                   u.nombre || ' ' || u.apellido AS nombre_completo,
                   p.monto, p.moneda, p.pasarela, p.estado, p.tipo,
                   p.fecha_aprobacion, p.created_at
            FROM pagos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE {where}
            ORDER BY p.created_at DESC
        """), params).fetchall()

        return [
            {
                "id": r.id,
                "nombre_completo": r.nombre_completo,
                "monto": float(r.monto) if r.monto is not None else None,
                "moneda": r.moneda,
                "pasarela": r.pasarela,
                "estado": r.estado,
                "tipo": r.tipo,
                "fecha_aprobacion": r.fecha_aprobacion.isoformat() if r.fecha_aprobacion else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Resumen facturación ───────────────────────────────────────────────────────

@router.get("/resumen")
def resumen_facturacion(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        mes_actual = db.execute(text("""
            SELECT
                COALESCE(SUM(monto) FILTER (WHERE estado = 'aprobado'), 0) AS total,
                COUNT(*) FILTER (WHERE estado = 'aprobado') AS aprobados,
                COUNT(*) FILTER (WHERE estado = 'rechazado') AS rechazados
            FROM pagos
            WHERE created_at >= DATE_TRUNC('month', NOW())
        """)).fetchone()

        mes_anterior = db.execute(text("""
            SELECT COALESCE(SUM(monto), 0) AS total FROM pagos
            WHERE estado = 'aprobado'
            AND created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
            AND created_at < DATE_TRUNC('month', NOW())
        """)).fetchone()

        total_actual = float(mes_actual.total)
        total_ant = float(mes_anterior.total)
        variacion = round((total_actual - total_ant) / total_ant * 100, 2) if total_ant > 0 else 0

        por_pasarela = db.execute(text("""
            SELECT pasarela,
                   COALESCE(SUM(monto), 0) AS total,
                   COUNT(*) AS cantidad
            FROM pagos
            WHERE estado = 'aprobado'
            AND created_at >= DATE_TRUNC('month', NOW())
            GROUP BY pasarela
            ORDER BY total DESC
        """)).fetchall()

        return {
            "total_recaudado_mes": total_actual,
            "total_recaudado_mes_anterior": total_ant,
            "variacion": variacion,
            "pagos_aprobados_mes": mes_actual.aprobados,
            "pagos_rechazados_mes": mes_actual.rechazados,
            "por_pasarela": [
                {"pasarela": r.pasarela, "total": float(r.total), "cantidad": r.cantidad}
                for r in por_pasarela
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Facturas ─────────────────────────────────────────────────────────────────

@router.get("/facturas")
def listar_facturas(
    tipo: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        condiciones = ["1=1"]
        params: dict = {}

        if tipo:
            condiciones.append("f.tipo = :tipo")
            params["tipo"] = tipo
        if mes:
            condiciones.append("TO_CHAR(f.fecha_emision, 'YYYY-MM') = :mes")
            params["mes"] = mes

        where = " AND ".join(condiciones)

        rows = db.execute(text(f"""
            SELECT id, numero_factura, tipo, razon_social,
                   monto_total, estado, fecha_emision
            FROM facturas f
            WHERE {where}
            ORDER BY fecha_emision DESC
        """), params).fetchall()

        return [
            {
                "id": r.id,
                "numero_factura": r.numero_factura,
                "tipo": r.tipo,
                "razon_social": r.razon_social,
                "monto_total": float(r.monto_total) if r.monto_total is not None else None,
                "estado": r.estado,
                "fecha_emision": r.fecha_emision.isoformat() if r.fecha_emision else None,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Pago manual ──────────────────────────────────────────────────────────────

@router.post("/pagos/manual")
def pago_manual(
    datos: PagoManual,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        plan = db.execute(
            text("SELECT id, precio_mensual FROM planes WHERE id = :id AND activo = true"),
            {"id": datos.plan_id}
        ).fetchone()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado o inactivo")

        pago = db.execute(text("""
            INSERT INTO pagos (usuario_id, monto, pasarela, estado, tipo, fecha_aprobacion)
            VALUES (:usuario_id, :monto, 'manual', 'aprobado', :tipo, NOW())
            RETURNING id
        """), {
            "usuario_id": datos.usuario_id,
            "monto": datos.monto,
            "tipo": datos.descripcion or "pago_manual",
        }).fetchone()

        suscripcion_pendiente = db.execute(text("""
            SELECT id FROM suscripciones
            WHERE usuario_id = :uid AND estado = 'pendiente_pago'
            ORDER BY created_at DESC LIMIT 1
        """), {"uid": datos.usuario_id}).fetchone()

        suscripcion_id = None
        if suscripcion_pendiente:
            db.execute(
                text("UPDATE suscripciones SET estado = 'activa' WHERE id = :id"),
                {"id": suscripcion_pendiente.id}
            )
            suscripcion_id = suscripcion_pendiente.id
        else:
            nueva = db.execute(text("""
                INSERT INTO suscripciones
                  (usuario_id, plan_id, estado, fecha_inicio, precio_pagado)
                VALUES (:uid, :plan_id, 'activa', CURRENT_DATE, :precio)
                RETURNING id
            """), {
                "uid": datos.usuario_id,
                "plan_id": datos.plan_id,
                "precio": datos.monto,
            }).fetchone()
            suscripcion_id = nueva.id

        db.commit()
        return {
            "pago_id": pago.id,
            "suscripcion_id": suscripcion_id,
            "mensaje": "Pago manual registrado y suscripción activada correctamente",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Exportar Mediquo ──────────────────────────────────────────────────────────

@router.get("/exportar-mediquo")
def exportar_mediquo(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
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

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Suscriptores"
        ws.append(["Nombre", "Apellido", "Email", "Teléfono", "DNI",
                   "Fecha Nacimiento", "Plan", "Estado", "Fecha Suscripción"])

        for r in rows:
            ws.append([
                r.nombre, r.apellido, r.email, r.telefono,
                r.dni if r.dni is not None else "",
                r.fecha_nacimiento.isoformat() if r.fecha_nacimiento else "",
                r.plan_nombre, r.estado,
                r.fecha_inicio.isoformat() if r.fecha_inicio else "",
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        fecha_hoy = date.today().isoformat()
        return Response(
            content=buffer.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=suscriptores_{fecha_hoy}.xlsx"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Historial exportaciones ───────────────────────────────────────────────────

@router.get("/historial-exportaciones")
def historial_exportaciones(
    _: int = Depends(require_admin)
):
    return []
