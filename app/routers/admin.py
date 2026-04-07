import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.auth import get_current_user
from datetime import date, timedelta
import io
import json
import openpyxl

logger = logging.getLogger(__name__)

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


# ══ DASHBOARD Y MÉTRICAS ══

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

        pendientes_pago = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones WHERE estado = 'pendiente_pago'
        """)).fetchone()

        revenue_por_plan = db.execute(text("""
            SELECT p.nombre, COUNT(s.id) as suscriptores,
                   COALESCE(SUM(s.precio_pagado), 0) as revenue
            FROM planes p
            LEFT JOIN suscripciones s ON p.id = s.plan_id
              AND s.estado IN ('activa', 'pendiente_pago')
            GROUP BY p.nombre
        """)).fetchall()

        nuevos_registros_hoy = db.execute(text("""
            SELECT COUNT(*) as total FROM usuarios
            WHERE DATE(created_at) = CURRENT_DATE
        """)).fetchone()

        ultimas_suscripciones = db.execute(text("""
            SELECT s.id,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email,
                   p.nombre AS plan_nombre,
                   s.estado, s.created_at
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            ORDER BY s.created_at DESC LIMIT 5
        """)).fetchall()

        mrr_empresarial = db.execute(text("""
            SELECT COALESCE(SUM(precio_total), 0) as mrr
            FROM suscripciones_empresariales WHERE estado = 'activa'
        """)).fetchone()

        empresas_activas = db.execute(text("""
            SELECT COUNT(*) as total FROM empresas WHERE activo = true
        """)).fetchone()

        empleados_activos = db.execute(text("""
            SELECT COUNT(*) as total FROM empleados_empresa WHERE activo = true
        """)).fetchone()

        ultimas_actividades = db.execute(text("""
            SELECT accion, tabla_afectada, created_at
            FROM auditoria ORDER BY created_at DESC LIMIT 10
        """)).fetchall()

        mrr_val = float(mrr.mrr)

        return {
            "mrr": mrr_val,
            "mrr_personal": mrr_val,
            "mrr_empresarial": float(mrr_empresarial.mrr),
            "arr": round(mrr_val * 12, 2),
            "suscriptores_activos": activos.total,
            "nuevos_hoy": nuevos_hoy.total,
            "nuevas_suscripciones_semana": nuevas_semana.total,
            "cancelaciones_mes": cancelaciones.total,
            "churn_rate": churn_rate,
            "churn_rate_porcentaje": churn_rate,
            "total_usuarios": total_usuarios.total,
            "usuarios_sin_convertir": sin_suscripcion.total,
            "tasa_conversion": round((activos.total / total_usuarios.total * 100), 2) if total_usuarios.total > 0 else 0,
            "pendientes_pago": pendientes_pago.total,
            "registros_hoy": nuevos_registros_hoy.total,
            "nuevos_registros_hoy": nuevos_registros_hoy.total,
            "empresas_activas": empresas_activas.total,
            "empleados_activos": empleados_activos.total,
            "popularidad_planes": [{"plan": p.nombre, "suscriptores": p.suscriptores} for p in planes],
            "revenue_por_plan": [
                {"plan": r.nombre, "suscriptores": r.suscriptores, "revenue": float(r.revenue)}
                for r in revenue_por_plan
            ],
            "ultimas_suscripciones": [
                {
                    "id": r.id,
                    "usuario_nombre": r.usuario_nombre,
                    "usuario_email": r.usuario_email,
                    "plan_nombre": r.plan_nombre,
                    "estado": r.estado,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in ultimas_suscripciones
            ],
            "ultimas_actividades": [
                {
                    "accion": a.accion,
                    "tabla_afectada": a.tabla_afectada,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in ultimas_actividades
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


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


# ══ GESTIÓN DE USUARIOS ══

@router.get("/usuarios")
def listar_usuarios(
    buscar: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        params: dict = {"limit": limit, "offset": offset}
        if buscar:
            params["q"] = f"%{buscar}%"
            rows = db.execute(text("""
                SELECT id, nombre, apellido, email, telefono, dni,
                       fecha_nacimiento, rol, activo, created_at,
                       plan_nombre, estado_suscripcion
                FROM (
                    SELECT u.id, u.nombre, u.apellido, u.email, u.telefono, u.dni,
                           u.fecha_nacimiento, u.rol, u.activo, u.created_at,
                           sub.plan_nombre, sub.estado_suscripcion
                    FROM usuarios u
                    LEFT JOIN LATERAL (
                        SELECT p.nombre AS plan_nombre,
                               s.estado AS estado_suscripcion
                        FROM suscripciones s
                        JOIN planes p ON p.id = s.plan_id
                        WHERE s.usuario_id = u.id
                        ORDER BY
                            CASE s.estado
                                WHEN 'activa' THEN 1
                                WHEN 'pendiente_pago' THEN 2
                                ELSE 3
                            END,
                            COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                            s.created_at DESC
                        LIMIT 1
                    ) sub ON true
                ) usuarios_con_suscripcion
                WHERE nombre ILIKE :q OR apellido ILIKE :q OR email ILIKE :q
                ORDER BY created_at DESC LIMIT :limit OFFSET :offset
            """), params).fetchall()
        else:
            rows = db.execute(text("""
                SELECT id, nombre, apellido, email, telefono, dni,
                       fecha_nacimiento, rol, activo, created_at,
                       plan_nombre, estado_suscripcion
                FROM (
                    SELECT u.id, u.nombre, u.apellido, u.email, u.telefono, u.dni,
                           u.fecha_nacimiento, u.rol, u.activo, u.created_at,
                           sub.plan_nombre, sub.estado_suscripcion
                    FROM usuarios u
                    LEFT JOIN LATERAL (
                        SELECT p.nombre AS plan_nombre,
                               s.estado AS estado_suscripcion
                        FROM suscripciones s
                        JOIN planes p ON p.id = s.plan_id
                        WHERE s.usuario_id = u.id
                        ORDER BY
                            CASE s.estado
                                WHEN 'activa' THEN 1
                                WHEN 'pendiente_pago' THEN 2
                                ELSE 3
                            END,
                            COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                            s.created_at DESC
                        LIMIT 1
                    ) sub ON true
                ) usuarios_con_suscripcion
                ORDER BY created_at DESC LIMIT :limit OFFSET :offset
            """), params).fetchall()

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
                "plan_nombre": r.plan_nombre,
                "estado_suscripcion": r.estado_suscripcion,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/usuarios/{target_usuario_id}")
def detalle_usuario(
    target_usuario_id: int,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        usuario = db.execute(text("""
            SELECT u.id, u.nombre, u.apellido, u.email, u.telefono, u.dni,
                   u.fecha_nacimiento, u.cuit, u.direccion, u.localidad,
                   u.codigo_postal, u.provincia, u.pais, u.rol, u.activo, u.created_at,
                   sub.suscripcion_id, sub.plan_id, sub.plan_nombre,
                   sub.estado_suscripcion, sub.fecha_inicio_suscripcion,
                   sub.fecha_vencimiento, sub.max_beneficiarios
            FROM usuarios u
            LEFT JOIN LATERAL (
                SELECT s.id AS suscripcion_id,
                       s.plan_id,
                       p.nombre AS plan_nombre,
                       s.estado AS estado_suscripcion,
                       s.fecha_inicio AS fecha_inicio_suscripcion,
                       s.fecha_vencimiento,
                       p.max_beneficiarios
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                WHERE s.usuario_id = u.id
                ORDER BY
                    CASE s.estado
                        WHEN 'activa' THEN 1
                        WHEN 'pendiente_pago' THEN 2
                        ELSE 3
                    END,
                    COALESCE(s.fecha_vencimiento, s.created_at) DESC,
                    s.created_at DESC
                LIMIT 1
            ) sub ON true
            WHERE u.id = :usuario_id
        """), {"usuario_id": target_usuario_id}).fetchone()

        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        beneficiarios_rows = []
        if usuario.suscripcion_id:
            beneficiarios_rows = db.execute(text("""
                SELECT id, nombre, apellido, dni, fecha_nacimiento, relacion
                FROM beneficiarios
                WHERE suscripcion_id = :suscripcion_id
                ORDER BY created_at ASC
            """), {"suscripcion_id": usuario.suscripcion_id}).fetchall()

        return {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "telefono": usuario.telefono,
            "dni": usuario.dni if usuario.dni is not None else "",
            "fecha_nacimiento": usuario.fecha_nacimiento.isoformat() if usuario.fecha_nacimiento else None,
            "cuit": usuario.cuit,
            "direccion": usuario.direccion,
            "localidad": usuario.localidad,
            "codigo_postal": usuario.codigo_postal,
            "provincia": usuario.provincia,
            "pais": usuario.pais,
            "rol": usuario.rol,
            "activo": usuario.activo,
            "created_at": usuario.created_at.isoformat() if usuario.created_at else None,
            "suscripcion_id": usuario.suscripcion_id,
            "plan_id": usuario.plan_id,
            "plan_nombre": usuario.plan_nombre,
            "estado_suscripcion": usuario.estado_suscripcion,
            "fecha_inicio_suscripcion": usuario.fecha_inicio_suscripcion.isoformat() if usuario.fecha_inicio_suscripcion else None,
            "fecha_vencimiento": usuario.fecha_vencimiento.isoformat() if usuario.fecha_vencimiento else None,
            "max_beneficiarios": usuario.max_beneficiarios,
            "beneficiarios": [
                {
                    "id": item.id,
                    "nombre": item.nombre,
                    "apellido": item.apellido,
                    "dni": item.dni,
                    "fecha_nacimiento": item.fecha_nacimiento.isoformat() if item.fecha_nacimiento else None,
                    "relacion": item.relacion,
                }
                for item in beneficiarios_rows
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ══ GESTIÓN DE SUSCRIPCIONES ══

@router.get("/suscripciones")
def listar_suscripciones(
    estado: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        filtro = "AND s.estado = :estado" if estado else ""
        params: dict = {"limit": limit, "offset": offset}
        if estado:
            params["estado"] = estado

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
            ORDER BY s.created_at DESC LIMIT :limit OFFSET :offset
        """), params).fetchall()

        return [
            {
                "id": r.id,
                "nombre_completo": r.usuario_nombre,
                "email": r.usuario_email,
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
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# Movido a /admin/facturacion/exportar-mediquo

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
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


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
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ══ ALERTAS ══

@router.get("/alertas")
def obtener_alertas(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(require_admin)
):
    try:
        pendientes = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones WHERE estado = 'pendiente_pago'
        """)).fetchone().total

        sin_convertir = db.execute(text("""
            SELECT COUNT(*) as total FROM usuarios
            WHERE activo = true
            AND created_at <= NOW() - INTERVAL '7 days'
            AND id NOT IN (
                SELECT usuario_id FROM suscripciones
                WHERE estado IN ('activa', 'pendiente_pago')
            )
        """)).fetchone().total

        exportar_mediquo = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE DATE(created_at) = CURRENT_DATE
        """)).fetchone().total

        alertas = []
        if pendientes > 0:
            alertas.append({
                "tipo": "pendientes_pago",
                "cantidad": pendientes,
                "mensaje": f"{pendientes} suscripciones pendientes de pago",
            })
        if sin_convertir > 0:
            alertas.append({
                "tipo": "sin_convertir",
                "cantidad": sin_convertir,
                "mensaje": f"{sin_convertir} usuarios sin suscripción hace más de 7 días",
            })
        if exportar_mediquo > 0:
            alertas.append({
                "tipo": "exportar_mediquo",
                "cantidad": exportar_mediquo,
                "mensaje": f"{exportar_mediquo} nuevos suscriptores para exportar a Mediquo hoy",
            })

        empresas_vencimiento = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones_empresariales
            WHERE estado NOT IN ('cancelada', 'vencida')
            AND proximo_cobro BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
        """)).fetchone().total

        empresas_pendiente = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones_empresariales
            WHERE estado = 'pendiente_pago'
        """)).fetchone().total

        if empresas_vencimiento > 0:
            alertas.append({
                "tipo": "empresas_vencimiento_7_dias",
                "cantidad": empresas_vencimiento,
                "mensaje": f"{empresas_vencimiento} empresas vencen en los próximos 7 días",
            })
        if empresas_pendiente > 0:
            alertas.append({
                "tipo": "empresas_pendiente_pago",
                "cantidad": empresas_pendiente,
                "mensaje": f"{empresas_pendiente} empresas con pago pendiente",
            })

        vencidas_3dias = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE estado = 'pendiente_pago'
            AND created_at <= NOW() - INTERVAL '3 days'
        """)).fetchone().total

        if vencidas_3dias > 0:
            alertas.append({
                "tipo": "suscripciones_vencidas_3dias",
                "cantidad": vencidas_3dias,
                "mensaje": f"{vencidas_3dias} suscripciones pendientes hace más de 3 días",
            })

        vencen_semana = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones
            WHERE estado = 'activa'
              AND fecha_vencimiento BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
        """)).fetchone().total

        if vencen_semana > 0:
            alertas.append({
                "tipo": "vencen_esta_semana",
                "cantidad": vencen_semana,
                "mensaje": f"{vencen_semana} suscripciones activas vencen en los próximos 7 días",
            })

        return alertas
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ─── Cambiar estado usuario ────────────────────────────────────────────────────

class CambiarEstadoUsuario(BaseModel):
    activo: bool
    motivo: Optional[str] = None


@router.put("/usuarios/{usuario_id}/estado")
def cambiar_estado_usuario(
    usuario_id: int,
    datos: CambiarEstadoUsuario,
    db: Session = Depends(get_db),
    _admin_id: int = Depends(require_admin)
):
    try:
        usuario = db.execute(
            text("SELECT id, nombre, apellido, email, activo, rol FROM usuarios WHERE id = :id"),
            {"id": usuario_id}
        ).fetchone()

        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        estado_anterior = usuario.activo

        db.execute(
            text("UPDATE usuarios SET activo = :activo WHERE id = :id"),
            {"activo": datos.activo, "id": usuario_id}
        )

        accion = "dar_de_alta" if datos.activo else "dar_de_baja"
        db.execute(text("""
            INSERT INTO auditoria (accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos)
            VALUES (:accion, 'usuarios', :registro_id, :datos_anteriores, :datos_nuevos)
        """), {
            "accion": accion,
            "registro_id": usuario_id,
            "datos_anteriores": json.dumps({"activo": estado_anterior}),
            "datos_nuevos": json.dumps({"activo": datos.activo, "motivo": datos.motivo}),
        })

        db.commit()

        return {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "activo": datos.activo,
            "rol": usuario.rol,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ─── Cambiar estado suscripción ────────────────────────────────────────────────

ESTADOS_PERMITIDOS = {"activa", "cancelada", "pendiente_pago", "vencida"}


class CambiarEstadoSuscripcion(BaseModel):
    estado: str
    motivo: Optional[str] = None


@router.put("/suscripciones/{suscripcion_id}/estado")
def cambiar_estado_suscripcion(
    suscripcion_id: int,
    datos: CambiarEstadoSuscripcion,
    db: Session = Depends(get_db),
    _admin_id: int = Depends(require_admin)
):
    try:
        if datos.estado not in ESTADOS_PERMITIDOS:
            raise HTTPException(
                status_code=400,
                detail=f"Estado inválido. Permitidos: {', '.join(ESTADOS_PERMITIDOS)}"
            )

        row = db.execute(text("""
            SELECT s.id, s.estado, s.precio_pagado, s.fecha_inicio,
                   u.nombre || ' ' || u.apellido AS usuario_nombre,
                   u.email AS usuario_email,
                   p.nombre AS plan_nombre
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE s.id = :id
        """), {"id": suscripcion_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Suscripción no encontrada")

        estado_anterior = row.estado

        db.execute(
            text("UPDATE suscripciones SET estado = :estado WHERE id = :id"),
            {"estado": datos.estado, "id": suscripcion_id}
        )

        if datos.estado == "activa" and estado_anterior != "activa":
            try:
                venc = db.execute(
                    text("SELECT fecha_vencimiento FROM suscripciones WHERE id = :id"),
                    {"id": suscripcion_id}
                ).fetchone()
                fecha_venc_str = venc.fecha_vencimiento.isoformat() if venc and venc.fecha_vencimiento else "—"
                precio = float(row.precio_pagado) if row.precio_pagado is not None else 0.0
                from app.services.email import enviar_email_suscripcion_activa
                enviar_email_suscripcion_activa(
                    row.usuario_email, row.usuario_nombre.split()[0],
                    row.plan_nombre, fecha_venc_str, precio
                )
            except Exception as e:
                logger.error("Error enviando email activacion suscripcion: %s", e)

        db.execute(text("""
            INSERT INTO historial_suscripciones
              (suscripcion_id, campo_modificado, valor_anterior, valor_nuevo, motivo)
            VALUES (:suscripcion_id, 'estado', :valor_anterior, :valor_nuevo, :motivo)
        """), {
            "suscripcion_id": suscripcion_id,
            "valor_anterior": estado_anterior,
            "valor_nuevo": datos.estado,
            "motivo": datos.motivo,
        })

        db.commit()

        return {
            "id": row.id,
            "usuario_nombre": row.usuario_nombre,
            "usuario_email": row.usuario_email,
            "plan_nombre": row.plan_nombre,
            "estado": datos.estado,
            "precio_pagado": float(row.precio_pagado) if row.precio_pagado is not None else None,
            "fecha_inicio": row.fecha_inicio.isoformat() if row.fecha_inicio else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ══ REPORTES ══

@router.get("/metricas-retencion")
def metricas_retencion(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        rows = db.execute(text("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', s.created_at), 'YYYY-MM') AS mes,
                COUNT(*) AS nuevos,
                COUNT(*) FILTER (WHERE s.estado = 'activa') AS activos_siguiente_mes
            FROM suscripciones s
            WHERE s.created_at >= DATE_TRUNC('month', NOW()) - INTERVAL '5 months'
            GROUP BY DATE_TRUNC('month', s.created_at)
            ORDER BY DATE_TRUNC('month', s.created_at) ASC
        """)).fetchall()

        resultado = []
        for r in rows:
            tasa = round((r.activos_siguiente_mes / r.nuevos * 100), 2) if r.nuevos > 0 else 0
            resultado.append({
                "mes": r.mes,
                "nuevos": r.nuevos,
                "activos_al_mes_siguiente": r.activos_siguiente_mes,
                "tasa_retencion": tasa,
            })
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ─── Métricas embudo ───────────────────────────────────────────────────────────

@router.get("/metricas-embudo")
def metricas_embudo(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        total_usuarios = db.execute(text(
            "SELECT COUNT(*) as total FROM usuarios"
        )).fetchone().total

        iniciaron_checkout = db.execute(text("""
            SELECT COUNT(DISTINCT usuario_id) as total FROM suscripciones
        """)).fetchone().total

        completaron_pago = db.execute(text("""
            SELECT COUNT(*) as total FROM suscripciones WHERE estado = 'activa'
        """)).fetchone().total

        tasa_reg_checkout = round(iniciaron_checkout / total_usuarios * 100, 2) if total_usuarios > 0 else 0
        tasa_checkout_pago = round(completaron_pago / iniciaron_checkout * 100, 2) if iniciaron_checkout > 0 else 0

        return {
            "visitantes_registrados": total_usuarios,
            "iniciaron_checkout": iniciaron_checkout,
            "completaron_pago": completaron_pago,
            "tasa_registro_a_checkout": tasa_reg_checkout,
            "tasa_checkout_a_pago": tasa_checkout_pago,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ─── Reporte mensual ───────────────────────────────────────────────────────────

@router.get("/reporte-mensual")
def reporte_mensual(
    mes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        from datetime import datetime
        if mes:
            try:
                inicio_mes = datetime.strptime(mes, "%Y-%m").date().replace(day=1)
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de mes inválido. Usar: YYYY-MM")
        else:
            hoy = date.today()
            inicio_mes = hoy.replace(day=1)

        # Calcular inicio del mes anterior
        if inicio_mes.month == 1:
            inicio_mes_ant = inicio_mes.replace(year=inicio_mes.year - 1, month=12)
        else:
            inicio_mes_ant = inicio_mes.replace(month=inicio_mes.month - 1)

        # Calcular fin del mes actual
        if inicio_mes.month == 12:
            fin_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1)
        else:
            fin_mes = inicio_mes.replace(month=inicio_mes.month + 1)

        def _mrr(desde, hasta):
            return float(db.execute(text("""
                SELECT COALESCE(SUM(precio_pagado), 0) as mrr FROM suscripciones
                WHERE estado = 'activa'
                AND created_at >= :desde AND created_at < :hasta
            """), {"desde": desde, "hasta": hasta}).fetchone().mrr)

        def _count(tabla_campo, desde, hasta, extra=""):
            return db.execute(text(f"""
                SELECT COUNT(*) as total FROM {tabla_campo}
                WHERE created_at >= :desde AND created_at < :hasta {extra}
            """), {"desde": desde, "hasta": hasta}).fetchone().total

        mrr_mes = _mrr(inicio_mes, fin_mes)
        mrr_ant = _mrr(inicio_mes_ant, inicio_mes)
        var_mrr = round((mrr_mes - mrr_ant) / mrr_ant * 100, 2) if mrr_ant > 0 else 0

        nuevas = _count("suscripciones", inicio_mes, fin_mes)
        nuevas_ant = _count("suscripciones", inicio_mes_ant, inicio_mes)
        var_nuevas = round((nuevas - nuevas_ant) / nuevas_ant * 100, 2) if nuevas_ant > 0 else 0

        canceladas = _count("suscripciones", inicio_mes, fin_mes, "AND estado = 'cancelada'")
        canceladas_ant = _count("suscripciones", inicio_mes_ant, inicio_mes, "AND estado = 'cancelada'")
        var_cancel = round((canceladas - canceladas_ant) / canceladas_ant * 100, 2) if canceladas_ant > 0 else 0

        nuevos_usuarios = _count("usuarios", inicio_mes, fin_mes)

        empresas_nuevas = db.execute(text("""
            SELECT COUNT(*) as total FROM empresas
            WHERE created_at >= :desde AND created_at < :hasta
        """), {"desde": inicio_mes, "hasta": fin_mes}).fetchone().total

        revenue_plan = db.execute(text("""
            SELECT p.nombre, COALESCE(SUM(s.precio_pagado), 0) as revenue,
                   COUNT(s.id) as suscriptores
            FROM planes p
            LEFT JOIN suscripciones s ON s.plan_id = p.id
                AND s.created_at >= :desde AND s.created_at < :hasta
            GROUP BY p.nombre
            ORDER BY revenue DESC
        """), {"desde": inicio_mes, "hasta": fin_mes}).fetchall()

        top_plan = revenue_plan[0].nombre if revenue_plan and revenue_plan[0].revenue > 0 else None

        return {
            "mes": inicio_mes.strftime("%Y-%m"),
            "mrr": mrr_mes,
            "mrr_mes_anterior": mrr_ant,
            "variacion_mrr": var_mrr,
            "nuevas_suscripciones": nuevas,
            "nuevas_mes_anterior": nuevas_ant,
            "variacion_nuevas": var_nuevas,
            "cancelaciones": canceladas,
            "cancelaciones_mes_anterior": canceladas_ant,
            "variacion_cancelaciones": var_cancel,
            "nuevos_usuarios": nuevos_usuarios,
            "empresas_nuevas": empresas_nuevas,
            "revenue_por_plan": [
                {"plan": r.nombre, "revenue": float(r.revenue), "suscriptores": r.suscriptores}
                for r in revenue_plan
            ],
            "top_plan": top_plan,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ══ VENCIMIENTOS AUTOMÁTICOS ══

@router.post("/procesar-vencimientos")
def procesar_vencimientos(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    """Pasa a 'vencida' las suscripciones activas cuya fecha_vencimiento ya pasó."""
    try:
        vencidas = db.execute(text("""
            SELECT s.id, u.email, u.nombre, p.nombre AS plan_nombre
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE s.estado = 'activa'
              AND s.fecha_vencimiento < CURRENT_DATE
        """)).fetchall()

        if not vencidas:
            return {"procesadas": 0}

        ids = [r.id for r in vencidas]
        db.execute(
            text("UPDATE suscripciones SET estado = 'vencida' WHERE id = ANY(:ids)"),
            {"ids": ids}
        )
        db.commit()

        from app.services.email import enviar_email_plan_vencido
        for r in vencidas:
            try:
                enviar_email_plan_vencido(r.email, r.nombre, r.plan_nombre)
            except Exception as e:
                logger.error("Error enviando email vencido a %s: %s", r.email, e)

        return {"procesadas": len(vencidas)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en procesar_vencimientos: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("/enviar-recordatorios")
def enviar_recordatorios(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    """Envía email de aviso a suscriptores cuyo plan vence en los próximos 7 días."""
    try:
        proximas = db.execute(text("""
            SELECT s.id, s.fecha_vencimiento,
                   u.email, u.nombre,
                   p.nombre AS plan_nombre
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            WHERE s.estado = 'activa'
              AND s.fecha_vencimiento BETWEEN CURRENT_DATE + 1
                                          AND CURRENT_DATE + 7
        """)).fetchall()

        from app.services.email import enviar_email_vencimiento_proximo
        enviados = 0
        for r in proximas:
            try:
                dias = (r.fecha_vencimiento - date.today()).days
                enviar_email_vencimiento_proximo(
                    r.email, r.nombre, r.plan_nombre,
                    dias, r.fecha_vencimiento.isoformat()
                )
                enviados += 1
            except Exception as e:
                logger.error("Error enviando recordatorio a %s: %s", r.email, e)

        return {"enviados": enviados}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en enviar_recordatorios: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
