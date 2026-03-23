from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.auth import get_current_user
from datetime import date, timedelta
import io
import openpyxl

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)


def require_admin(db: Session = Depends(get_db), usuario_id: int = Depends(get_current_user)):
    usuario = db.execute(
        text("SELECT rol FROM usuarios WHERE id = :id"),
        {"id": usuario_id}
    ).fetchone()
    if not usuario or usuario.rol != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: se requiere rol admin")
    return usuario_id


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        mrr = db.execute(text("""
            SELECT COALESCE(SUM(precio_pagado), 0) as mrr
            FROM suscripciones WHERE estado = 'activa'
        """)).fetchone()

        activos = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones WHERE estado = 'activa'
        """)).fetchone()

        nuevos_hoy = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE DATE(created_at) = CURRENT_DATE
        """)).fetchone()

        nuevas_semana = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """)).fetchone()

        cancelaciones = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE estado = 'cancelada'
            AND created_at >= DATE_TRUNC('month', NOW())
        """)).fetchone()

        total_usuarios = db.execute(text("""
            SELECT COUNT(*) as total FROM usuarios
        """)).fetchone()

        sin_suscripcion = db.execute(text("""
            SELECT COUNT(*) as total FROM usuarios
            WHERE id NOT IN (
                SELECT usuario_id FROM suscripciones WHERE estado = 'activa'
            )
        """)).fetchone()

        total_mes_anterior = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
            AND created_at < DATE_TRUNC('month', NOW())
        """)).fetchone()

        churn_rate = 0
        if total_mes_anterior.total > 0:
            churn_rate = round((cancelaciones.total / total_mes_anterior.total) * 100, 2)

        planes = db.execute(text("""
            SELECT p.nombre, COUNT(s.id) as suscriptores
            FROM planes p
            LEFT JOIN suscripciones s ON p.id = s.plan_id AND s.estado = 'activa'
            GROUP BY p.nombre
            ORDER BY suscriptores DESC
        """)).fetchall()

        return {
            "mrr": float(mrr.mrr),
            "suscriptores_activos": activos.total,
            "nuevos_hoy": nuevos_hoy.total,
            "nuevas_suscripciones_semana": nuevas_semana.total,
            "cancelaciones_mes": cancelaciones.total,
            "churn_rate": churn_rate,
            "churn_rate_porcentaje": churn_rate,
            "total_usuarios": total_usuarios.total,
            "usuarios_sin_convertir": sin_suscripcion.total,
            "tasa_conversion": round((activos.total / total_usuarios.total * 100), 2) if total_usuarios.total > 0 else 0,
            "popularidad_planes": [{"plan": p.nombre, "suscriptores": p.suscriptores} for p in planes]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Métricas gráfico ─────────────────────────────────────────────────────────

@router.get("/metricas-grafico")
def metricas_grafico(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        rows = db.execute(text("""
            SELECT DATE(created_at) as fecha, COUNT(*) as nuevas
            FROM suscripciones
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY fecha ASC
        """)).fetchall()

        por_dia = {row.fecha: row.nuevas for row in rows}

        total_previo = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE created_at < NOW() - INTERVAL '30 days'
        """)).fetchone().total

        resultado = []
        acumulado = total_previo
        hoy = date.today()
        inicio = hoy - timedelta(days=29)

        for i in range(30):
            dia = inicio + timedelta(days=i)
            nuevas = por_dia.get(dia, 0)
            acumulado += nuevas
            resultado.append({
                "fecha": dia.isoformat(),
                "nuevas": nuevas,
                "total_acumulado": acumulado
            })

        return resultado
    except HTTPException:
        raise
    except Exception:
        return []


# ─── Usuarios ─────────────────────────────────────────────────────────────────

@router.get("/usuarios")
def listar_usuarios(
    buscar: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        if buscar:
            rows = db.execute(text("""
                SELECT id, nombre, apellido, email, telefono, dni,
                       fecha_nacimiento, rol, activo, created_at
                FROM usuarios
                WHERE nombre ILIKE :q OR apellido ILIKE :q OR email ILIKE :q
                ORDER BY created_at DESC
            """), {"q": f"%{buscar}%"}).fetchall()
        else:
            rows = db.execute(text("""
                SELECT id, nombre, apellido, email, telefono, dni,
                       fecha_nacimiento, rol, activo, created_at
                FROM usuarios
                ORDER BY created_at DESC
            """)).fetchall()

        return [
            {
                "id": r.id,
                "nombre": r.nombre,
                "apellido": r.apellido,
                "email": r.email,
                "telefono": r.telefono,
                "dni": r.dni if r.dni is not None else "",
                "fecha_nacimiento": r.fecha_nacimiento.isoformat() if r.fecha_nacimiento else None,
                "rol": r.rol,
                "activo": r.activo,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Suscripciones ────────────────────────────────────────────────────────────

@router.get("/suscripciones")
def listar_suscripciones(
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        filtro = "AND s.estado = :estado" if estado else ""
        params = {"estado": estado} if estado else {}

        rows = db.execute(text(f"""
            SELECT s.id,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email,
                   p.nombre AS plan_nombre,
                   s.estado,
                   s.precio_pagado,
                   s.fecha_inicio,
                   s.created_at
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE 1=1 {filtro}
            ORDER BY s.created_at DESC
        """), params).fetchall()

        return [
            {
                "id": r.id,
                "usuario_nombre": r.usuario_nombre,
                "usuario_email": r.usuario_email,
                "plan_nombre": r.plan_nombre,
                "estado": r.estado,
                "precio_pagado": float(r.precio_pagado) if r.precio_pagado is not None else None,
                "fecha_inicio": r.fecha_inicio.isoformat() if r.fecha_inicio else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Exportar Excel ───────────────────────────────────────────────────────────

@router.get("/exportar-excel")
def exportar_excel(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
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

        headers = ["Nombre", "Apellido", "Email", "Teléfono", "DNI",
                   "Fecha Nacimiento", "Plan", "Estado", "Fecha Suscripción"]
        ws.append(headers)

        for r in rows:
            ws.append([
                r.nombre,
                r.apellido,
                r.email,
                r.telefono,
                r.dni if r.dni is not None else "",
                r.fecha_nacimiento.isoformat() if r.fecha_nacimiento else "",
                r.plan_nombre,
                r.estado,
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


# ─── Actualizar plan ──────────────────────────────────────────────────────────

class ActualizarPlan(BaseModel):
    activo: Optional[bool] = None
    precio_mensual: Optional[float] = None


@router.put("/planes/{plan_id}")
def actualizar_plan(
    plan_id: int,
    datos: ActualizarPlan,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        plan = db.execute(
            text("SELECT * FROM planes WHERE id = :id"),
            {"id": plan_id}
        ).fetchone()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")

        campos = []
        params = {"id": plan_id}

        if datos.activo is not None:
            campos.append("activo = :activo")
            params["activo"] = datos.activo

        if datos.precio_mensual is not None:
            campos.append("precio_mensual = :precio_mensual")
            params["precio_mensual"] = datos.precio_mensual

        if campos:
            db.execute(
                text(f"UPDATE planes SET {', '.join(campos)} WHERE id = :id"),
                params
            )
            db.commit()

        plan_actualizado = db.execute(
            text("SELECT * FROM planes WHERE id = :id"),
            {"id": plan_id}
        ).fetchone()

        return {
            "id": plan_actualizado.id,
            "nombre": plan_actualizado.nombre,
            "precio_mensual": float(plan_actualizado.precio_mensual),
            "activo": plan_actualizado.activo,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
