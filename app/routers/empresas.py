from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.auth import get_current_user
from app.routers.admin import require_admin
from datetime import date, timedelta
import io
import json
import openpyxl

router = APIRouter(
    prefix="/admin/empresas",
    tags=["empresas"]
)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class EmpresaCrear(BaseModel):
    razon_social: str
    cuit: str
    nombre_comercial: Optional[str] = None
    rubro: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    email_contacto: str
    contacto_nombre: str
    contacto_cargo: Optional[str] = None


class EmpresaActualizar(BaseModel):
    razon_social: Optional[str] = None
    cuit: Optional[str] = None
    nombre_comercial: Optional[str] = None
    rubro: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    telefono: Optional[str] = None
    email_contacto: Optional[str] = None
    contacto_nombre: Optional[str] = None
    contacto_cargo: Optional[str] = None


class CambiarEstadoEmpresa(BaseModel):
    activo: bool
    motivo: Optional[str] = None


class SuscripcionEmpresarialCrear(BaseModel):
    plan_id: int
    cantidad_empleados: int
    precio_por_empleado: float
    periodicidad: str
    fecha_inicio: date


class CambiarEstadoSuscripcionEmpresarial(BaseModel):
    estado: str
    motivo: Optional[str] = None


class EmpleadoCrear(BaseModel):
    nombre: str
    apellido: str
    dni: str
    email: str
    cargo: Optional[str] = None


class EmpleadoActualizar(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None


class CambiarEstadoEmpleado(BaseModel):
    activo: bool
    motivo: Optional[str] = None


class BulkEmpleados(BaseModel):
    datos: Optional[str] = None
    empleados: Optional[List[EmpleadoCrear]] = None


ESTADOS_SUSCRIPCION_EMPRESA = {"activa", "pendiente_pago", "cancelada", "vencida"}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _empresa_to_dict(row) -> dict:
    d = {k: (v.isoformat() if hasattr(v, "isoformat") else v)
         for k, v in row._mapping.items()}
    if "email_contacto" in d:
        d["contacto_email"] = d.pop("email_contacto")
    return d

def _calcular_fecha_fin(fecha_inicio: date, periodicidad: str) -> date:
    dias = {"mensual": 30, "trimestral": 90, "anual": 365}
    return fecha_inicio + timedelta(days=dias.get(periodicidad, 30))


def _registrar_auditoria(db: Session, accion: str, tabla: str, registro_id: int,
                          datos_anteriores: dict, datos_nuevos: dict):
    db.execute(text("""
        INSERT INTO auditoria (accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos)
        VALUES (:accion, :tabla, :registro_id, :datos_anteriores, :datos_nuevos)
    """), {
        "accion": accion,
        "tabla": tabla,
        "registro_id": registro_id,
        "datos_anteriores": json.dumps(datos_anteriores),
        "datos_nuevos": json.dumps(datos_nuevos),
    })


# ══════════════════════════════════════════
# SECCIÓN: GESTIÓN DE EMPRESAS
# ══════════════════════════════════════════

@router.get("")
def listar_empresas(
    activo: Optional[bool] = Query(None),
    buscar: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        condiciones = []
        params: dict = {}
        if activo is not None:
            condiciones.append("e.activo = :activo")
            params["activo"] = activo
        if buscar:
            condiciones.append("(e.razon_social ILIKE :q OR e.cuit ILIKE :q OR e.email_contacto ILIKE :q)")
            params["q"] = f"%{buscar}%"
        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

        rows = db.execute(text(f"""
            SELECT e.id, e.razon_social, e.cuit, e.nombre_comercial, e.rubro,
                   e.email_contacto, e.contacto_nombre, e.activo, e.created_at,
                   COUNT(em.id) FILTER (WHERE em.activo = true) AS cantidad_empleados_activos,
                   se.estado AS estado_suscripcion,
                   p.nombre AS plan_nombre,
                   se.proximo_cobro
            FROM empresas e
            LEFT JOIN empleados_empresa em ON em.empresa_id = e.id
            LEFT JOIN suscripciones_empresariales se
                   ON se.empresa_id = e.id AND se.estado NOT IN ('cancelada', 'vencida')
            LEFT JOIN planes p ON p.id = se.plan_id
            {where}
            GROUP BY e.id, e.razon_social, e.cuit, e.nombre_comercial, e.rubro,
                     e.email_contacto, e.contacto_nombre, e.activo, e.created_at,
                     se.estado, p.nombre, se.proximo_cobro
            ORDER BY e.created_at DESC
        """), params).fetchall()

        return [
            {
                "id": r.id,
                "razon_social": r.razon_social,
                "cuit": r.cuit,
                "nombre_comercial": r.nombre_comercial,
                "rubro": r.rubro,
                "contacto_email": r.email_contacto,
                "contacto_nombre": r.contacto_nombre,
                "activo": r.activo,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "cantidad_empleados_activos": r.cantidad_empleados_activos or 0,
                "estado_suscripcion": r.estado_suscripcion,
                "plan_nombre": r.plan_nombre,
                "proximo_cobro": r.proximo_cobro.isoformat() if r.proximo_cobro else None,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Crear empresa ─────────────────────────────────────────────────────────────

@router.post("")
def crear_empresa(
    datos: EmpresaCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        existente = db.execute(
            text("SELECT id FROM empresas WHERE cuit = :cuit"),
            {"cuit": datos.cuit}
        ).fetchone()
        if existente:
            raise HTTPException(status_code=400, detail="Ya existe una empresa con ese CUIT")

        result = db.execute(text("""
            INSERT INTO empresas
              (razon_social, cuit, nombre_comercial, rubro, direccion, localidad,
               provincia, telefono, email_contacto, contacto_nombre, contacto_cargo, activo)
            VALUES
              (:razon_social, :cuit, :nombre_comercial, :rubro, :direccion, :localidad,
               :provincia, :telefono, :email_contacto, :contacto_nombre, :contacto_cargo, true)
            RETURNING id
        """), {
            "razon_social": datos.razon_social,
            "cuit": datos.cuit,
            "nombre_comercial": datos.nombre_comercial,
            "rubro": datos.rubro,
            "direccion": datos.direccion,
            "localidad": datos.localidad,
            "provincia": datos.provincia,
            "telefono": datos.telefono,
            "email_contacto": datos.email_contacto,
            "contacto_nombre": datos.contacto_nombre,
            "contacto_cargo": datos.contacto_cargo,
        }).fetchone()
        db.commit()

        empresa = db.execute(
            text("SELECT * FROM empresas WHERE id = :id"),
            {"id": result.id}
        ).fetchone()

        return _empresa_to_dict(empresa)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Detalle empresa ───────────────────────────────────────────────────────────

@router.get("/{empresa_id}")
def detalle_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empresa = db.execute(
            text("SELECT * FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        suscripcion = db.execute(text("""
            SELECT se.*, p.nombre AS plan_nombre
            FROM suscripciones_empresariales se
            LEFT JOIN planes p ON p.id = se.plan_id
            WHERE se.empresa_id = :id
            ORDER BY se.created_at DESC LIMIT 1
        """), {"id": empresa_id}).fetchone()

        empleados = db.execute(text("""
            SELECT id, nombre, apellido, dni, email, cargo,
                   activo, fecha_alta, fecha_baja, usuario_id
            FROM empleados_empresa
            WHERE empresa_id = :id
            ORDER BY fecha_alta DESC
        """), {"id": empresa_id}).fetchall()

        empleados_activos = sum(1 for e in empleados if e.activo)

        meses_activa = 0
        proximo_vencimiento = None
        if suscripcion and suscripcion.fecha_inicio:
            delta = date.today() - suscripcion.fecha_inicio
            meses_activa = delta.days // 30
        if suscripcion and suscripcion.fecha_fin:
            proximo_vencimiento = suscripcion.fecha_fin.isoformat()

        return {
            "empresa": _empresa_to_dict(empresa),
            "suscripcion": {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                            for k, v in suscripcion._mapping.items()} if suscripcion else None,
            "empleados": [
                {
                    "id": e.id, "nombre": e.nombre, "apellido": e.apellido,
                    "dni": e.dni, "email": e.email, "cargo": e.cargo,
                    "activo": e.activo,
                    "fecha_alta": e.fecha_alta.isoformat() if e.fecha_alta else None,
                    "fecha_baja": e.fecha_baja.isoformat() if e.fecha_baja else None,
                    "usuario_id": e.usuario_id,
                }
                for e in empleados
            ],
            "metricas": {
                "empleados_activos": empleados_activos,
                "empleados_totales": len(empleados),
                "meses_activa": meses_activa,
                "proximo_vencimiento": proximo_vencimiento,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Actualizar empresa ────────────────────────────────────────────────────────

@router.put("/{empresa_id}")
def actualizar_empresa(
    empresa_id: int,
    datos: EmpresaActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empresa = db.execute(
            text("SELECT id FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        campos = []
        params = {"id": empresa_id}
        for campo, valor in datos.model_dump(exclude_none=True).items():
            campos.append(f"{campo} = :{campo}")
            params[campo] = valor

        if campos:
            db.execute(
                text(f"UPDATE empresas SET {', '.join(campos)} WHERE id = :id"),
                params
            )
            db.commit()

        actualizada = db.execute(
            text("SELECT * FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()

        return _empresa_to_dict(actualizada)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Cambiar estado empresa ────────────────────────────────────────────────────

@router.put("/{empresa_id}/estado")
def cambiar_estado_empresa(
    empresa_id: int,
    datos: CambiarEstadoEmpresa,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empresa = db.execute(
            text("SELECT id, razon_social, activo FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        db.execute(
            text("UPDATE empresas SET activo = :activo WHERE id = :id"),
            {"activo": datos.activo, "id": empresa_id}
        )

        if not datos.activo:
            db.execute(
                text("UPDATE empleados_empresa SET activo = false WHERE empresa_id = :id"),
                {"id": empresa_id}
            )
            db.execute(
                text("""UPDATE suscripciones_empresariales SET estado = 'cancelada'
                        WHERE empresa_id = :id AND estado NOT IN ('cancelada', 'vencida')"""),
                {"id": empresa_id}
            )
        else:
            db.execute(
                text("""UPDATE suscripciones_empresariales SET estado = 'pendiente_pago'
                        WHERE empresa_id = :id AND estado = 'cancelada'"""),
                {"id": empresa_id}
            )

        accion = "dar_de_alta_empresa" if datos.activo else "dar_de_baja_empresa"
        _registrar_auditoria(db, accion, "empresas", empresa_id,
                             {"activo": empresa.activo},
                             {"activo": datos.activo, "motivo": datos.motivo})
        db.commit()

        actualizada = db.execute(
            text("SELECT * FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()
        return _empresa_to_dict(actualizada)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════
# SECCIÓN: SUSCRIPCIONES EMPRESARIALES
# ══════════════════════════════════════════

@router.post("/{empresa_id}/suscripcion")
def crear_suscripcion_empresarial(
    empresa_id: int,
    datos: SuscripcionEmpresarialCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empresa = db.execute(
            text("SELECT id FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        if datos.periodicidad not in ("mensual", "trimestral", "anual"):
            raise HTTPException(status_code=400,
                                detail="Periodicidad inválida. Usar: mensual, trimestral, anual")

        fecha_fin = _calcular_fecha_fin(datos.fecha_inicio, datos.periodicidad)
        precio_total = datos.cantidad_empleados * datos.precio_por_empleado

        result = db.execute(text("""
            INSERT INTO suscripciones_empresariales
              (empresa_id, plan_id, cantidad_empleados, precio_por_empleado,
               precio_total, periodicidad, fecha_inicio, fecha_fin,
               proximo_cobro, estado)
            VALUES
              (:empresa_id, :plan_id, :cantidad_empleados, :precio_por_empleado,
               :precio_total, :periodicidad, :fecha_inicio, :fecha_fin,
               :proximo_cobro, 'activa')
            RETURNING id
        """), {
            "empresa_id": empresa_id,
            "plan_id": datos.plan_id,
            "cantidad_empleados": datos.cantidad_empleados,
            "precio_por_empleado": datos.precio_por_empleado,
            "precio_total": precio_total,
            "periodicidad": datos.periodicidad,
            "fecha_inicio": datos.fecha_inicio,
            "fecha_fin": fecha_fin,
            "proximo_cobro": fecha_fin,
        }).fetchone()
        db.commit()

        suscripcion = db.execute(
            text("SELECT * FROM suscripciones_empresariales WHERE id = :id"),
            {"id": result.id}
        ).fetchone()
        return {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                for k, v in suscripcion._mapping.items()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Cambiar estado suscripción empresarial ────────────────────────────────────

@router.put("/{empresa_id}/suscripcion/estado")
def cambiar_estado_suscripcion_empresarial(
    empresa_id: int,
    datos: CambiarEstadoSuscripcionEmpresarial,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        if datos.estado not in ESTADOS_SUSCRIPCION_EMPRESA:
            raise HTTPException(status_code=400,
                                detail=f"Estado inválido. Permitidos: {', '.join(ESTADOS_SUSCRIPCION_EMPRESA)}")

        suscripcion = db.execute(text("""
            SELECT id, estado FROM suscripciones_empresariales
            WHERE empresa_id = :id
            ORDER BY created_at DESC LIMIT 1
        """), {"id": empresa_id}).fetchone()
        if not suscripcion:
            raise HTTPException(status_code=404, detail="Suscripción empresarial no encontrada")

        estado_anterior = suscripcion.estado
        db.execute(
            text("UPDATE suscripciones_empresariales SET estado = :estado WHERE id = :id"),
            {"estado": datos.estado, "id": suscripcion.id}
        )

        if datos.estado in ("cancelada", "vencida"):
            db.execute(
                text("UPDATE empleados_empresa SET activo = false WHERE empresa_id = :id"),
                {"id": empresa_id}
            )
        elif datos.estado == "activa":
            db.execute(
                text("""UPDATE empleados_empresa SET activo = true, fecha_baja = null
                        WHERE empresa_id = :id"""),
                {"id": empresa_id}
            )

        db.execute(text("""
            INSERT INTO historial_suscripciones
              (suscripcion_id, campo_modificado, valor_anterior, valor_nuevo, motivo)
            VALUES (:sid, 'estado', :anterior, :nuevo, :motivo)
        """), {
            "sid": suscripcion.id,
            "anterior": estado_anterior,
            "nuevo": datos.estado,
            "motivo": datos.motivo,
        })
        db.commit()

        actualizada = db.execute(
            text("SELECT * FROM suscripciones_empresariales WHERE id = :id"),
            {"id": suscripcion.id}
        ).fetchone()
        return {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                for k, v in actualizada._mapping.items()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Ver suscripción empresarial ───────────────────────────────────────────────

@router.get("/{empresa_id}/suscripcion")
def ver_suscripcion_empresarial(
    empresa_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        row = db.execute(text("""
            SELECT se.id, p.nombre AS plan_nombre,
                   se.cantidad_empleados, se.precio_por_empleado, se.precio_total,
                   se.estado, se.periodicidad, se.fecha_inicio, se.fecha_fin,
                   se.proximo_cobro
            FROM suscripciones_empresariales se
            LEFT JOIN planes p ON p.id = se.plan_id
            WHERE se.empresa_id = :id
            ORDER BY se.created_at DESC LIMIT 1
        """), {"id": empresa_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Sin suscripción registrada")

        dias_para_vencer = None
        if row.fecha_fin:
            dias_para_vencer = (row.fecha_fin - date.today()).days

        return {
            "id": row.id,
            "plan_nombre": row.plan_nombre,
            "cantidad_empleados": row.cantidad_empleados,
            "precio_por_empleado": float(row.precio_por_empleado) if row.precio_por_empleado else None,
            "precio_total": float(row.precio_total) if row.precio_total else None,
            "estado": row.estado,
            "periodicidad": row.periodicidad,
            "fecha_inicio": row.fecha_inicio.isoformat() if row.fecha_inicio else None,
            "fecha_fin": row.fecha_fin.isoformat() if row.fecha_fin else None,
            "proximo_cobro": row.proximo_cobro.isoformat() if row.proximo_cobro else None,
            "dias_para_vencer": dias_para_vencer,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════
# SECCIÓN: GESTIÓN DE EMPLEADOS
# ══════════════════════════════════════════

@router.get("/{empresa_id}/empleados")
def listar_empleados(
    empresa_id: int,
    activo: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        filtro = "AND em.activo = :activo" if activo is not None else ""
        params = {"empresa_id": empresa_id}
        if activo is not None:
            params["activo"] = activo

        rows = db.execute(text(f"""
            SELECT id, nombre, apellido, dni, email, cargo,
                   activo, fecha_alta, fecha_baja, usuario_id
            FROM empleados_empresa
            WHERE empresa_id = :empresa_id {filtro}
            ORDER BY fecha_alta DESC
        """), params).fetchall()

        return [
            {
                "id": e.id, "nombre": e.nombre, "apellido": e.apellido,
                "dni": e.dni, "email": e.email, "cargo": e.cargo,
                "activo": e.activo,
                "fecha_alta": e.fecha_alta.isoformat() if e.fecha_alta else None,
                "fecha_baja": e.fecha_baja.isoformat() if e.fecha_baja else None,
                "usuario_id": e.usuario_id,
            }
            for e in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Agregar empleado ──────────────────────────────────────────────────────────

def _crear_empleado(empresa_id: int, datos: EmpleadoCrear, db: Session) -> dict:
    existente = db.execute(text("""
        SELECT id FROM empleados_empresa
        WHERE empresa_id = :empresa_id AND email = :email
    """), {"empresa_id": empresa_id, "email": datos.email}).fetchone()
    if existente:
        raise HTTPException(status_code=400,
                            detail=f"El email {datos.email} ya está registrado en esta empresa")

    usuario = db.execute(
        text("SELECT id FROM usuarios WHERE email = :email"),
        {"email": datos.email}
    ).fetchone()
    usuario_id = usuario.id if usuario else None

    result = db.execute(text("""
        INSERT INTO empleados_empresa
          (empresa_id, nombre, apellido, dni, email, cargo, activo, fecha_alta, usuario_id)
        VALUES
          (:empresa_id, :nombre, :apellido, :dni, :email, :cargo, true, CURRENT_DATE, :usuario_id)
        RETURNING id, nombre, apellido, dni, email, cargo, activo, fecha_alta, usuario_id
    """), {
        "empresa_id": empresa_id,
        "nombre": datos.nombre,
        "apellido": datos.apellido,
        "dni": datos.dni,
        "email": datos.email,
        "cargo": datos.cargo,
        "usuario_id": usuario_id,
    }).fetchone()

    return {
        "id": result.id, "nombre": result.nombre, "apellido": result.apellido,
        "dni": result.dni, "email": result.email, "cargo": result.cargo,
        "activo": result.activo,
        "fecha_alta": result.fecha_alta.isoformat() if result.fecha_alta else None,
        "usuario_id": result.usuario_id,
    }


@router.post("/{empresa_id}/empleados")
def agregar_empleado(
    empresa_id: int,
    datos: EmpleadoCrear,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empresa = db.execute(
            text("SELECT id FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        empleado = _crear_empleado(empresa_id, datos, db)
        db.commit()
        return empleado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Bulk empleados ────────────────────────────────────────────────────────────

@router.post("/{empresa_id}/empleados/bulk")
def agregar_empleados_bulk(
    empresa_id: int,
    datos: BulkEmpleados,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empresa = db.execute(
            text("SELECT id FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        # Determinar lista de empleados según formato recibido
        empleados_lista: List[EmpleadoCrear] = []

        if datos.datos:
            # Formato CSV texto: "Nombre,Apellido,DNI,Email,Cargo" por línea
            for linea in datos.datos.strip().splitlines():
                linea = linea.strip()
                if not linea:
                    continue
                partes = [p.strip() for p in linea.split(",")]
                if len(partes) < 4:
                    continue
                empleados_lista.append(EmpleadoCrear(
                    nombre=partes[0],
                    apellido=partes[1],
                    dni=partes[2],
                    email=partes[3],
                    cargo=partes[4] if len(partes) > 4 else None,
                ))
        elif datos.empleados:
            empleados_lista = datos.empleados
        else:
            raise HTTPException(status_code=400, detail="Debe enviar 'datos' (CSV) o 'empleados' (JSON)")

        if len(empleados_lista) > 500:
            raise HTTPException(status_code=400, detail="Máximo 500 empleados por request")

        cargados = 0
        errores = []

        for emp in empleados_lista:
            try:
                _crear_empleado(empresa_id, emp, db)
                cargados += 1
            except HTTPException as e:
                errores.append(f"{emp.email}: {e.detail}")
            except Exception as e:
                errores.append(f"{emp.email}: {str(e)}")

        db.commit()
        return {"cargados": cargados, "fallidos": len(errores), "errores": errores}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Actualizar empleado ───────────────────────────────────────────────────────

@router.put("/{empresa_id}/empleados/{empleado_id}")
def actualizar_empleado(
    empresa_id: int,
    empleado_id: int,
    datos: EmpleadoActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empleado = db.execute(
            text("SELECT id FROM empleados_empresa WHERE id = :id AND empresa_id = :empresa_id"),
            {"id": empleado_id, "empresa_id": empresa_id}
        ).fetchone()
        if not empleado:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        campos = []
        params = {"id": empleado_id}
        for campo, valor in datos.model_dump(exclude_none=True).items():
            campos.append(f"{campo} = :{campo}")
            params[campo] = valor

        if campos:
            db.execute(
                text(f"UPDATE empleados_empresa SET {', '.join(campos)} WHERE id = :id"),
                params
            )
            db.commit()

        actualizado = db.execute(text("""
            SELECT id, nombre, apellido, dni, email, cargo,
                   activo, fecha_alta, fecha_baja, usuario_id
            FROM empleados_empresa WHERE id = :id
        """), {"id": empleado_id}).fetchone()

        return {
            "id": actualizado.id, "nombre": actualizado.nombre,
            "apellido": actualizado.apellido, "dni": actualizado.dni,
            "email": actualizado.email, "cargo": actualizado.cargo,
            "activo": actualizado.activo,
            "fecha_alta": actualizado.fecha_alta.isoformat() if actualizado.fecha_alta else None,
            "fecha_baja": actualizado.fecha_baja.isoformat() if actualizado.fecha_baja else None,
            "usuario_id": actualizado.usuario_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Cambiar estado empleado ───────────────────────────────────────────────────

@router.put("/{empresa_id}/empleados/{empleado_id}/estado")
def cambiar_estado_empleado(
    empresa_id: int,
    empleado_id: int,
    datos: CambiarEstadoEmpleado,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empleado = db.execute(
            text("""SELECT id, activo FROM empleados_empresa
                    WHERE id = :id AND empresa_id = :empresa_id"""),
            {"id": empleado_id, "empresa_id": empresa_id}
        ).fetchone()
        if not empleado:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        if datos.activo:
            db.execute(text("""
                UPDATE empleados_empresa SET activo = true, fecha_baja = null
                WHERE id = :id
            """), {"id": empleado_id})
        else:
            db.execute(text("""
                UPDATE empleados_empresa SET activo = false, fecha_baja = CURRENT_DATE
                WHERE id = :id
            """), {"id": empleado_id})

        _registrar_auditoria(db, "cambiar_estado_empleado", "empleados_empresa",
                             empleado_id, {"activo": empleado.activo},
                             {"activo": datos.activo, "motivo": datos.motivo})
        db.commit()

        actualizado = db.execute(text("""
            SELECT id, nombre, apellido, dni, email, cargo,
                   activo, fecha_alta, fecha_baja, usuario_id
            FROM empleados_empresa WHERE id = :id
        """), {"id": empleado_id}).fetchone()

        return {
            "id": actualizado.id, "nombre": actualizado.nombre,
            "apellido": actualizado.apellido, "dni": actualizado.dni,
            "email": actualizado.email, "cargo": actualizado.cargo,
            "activo": actualizado.activo,
            "fecha_alta": actualizado.fecha_alta.isoformat() if actualizado.fecha_alta else None,
            "fecha_baja": actualizado.fecha_baja.isoformat() if actualizado.fecha_baja else None,
            "usuario_id": actualizado.usuario_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Eliminar empleado ─────────────────────────────────────────────────────────

@router.delete("/{empresa_id}/empleados/{empleado_id}")
def eliminar_empleado(
    empresa_id: int,
    empleado_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empleado = db.execute(
            text("""SELECT id, activo, fecha_alta FROM empleados_empresa
                    WHERE id = :id AND empresa_id = :empresa_id"""),
            {"id": empleado_id, "empresa_id": empresa_id}
        ).fetchone()
        if not empleado:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")

        if empleado.fecha_alta != date.today():
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar: usar dar de baja en su lugar"
            )

        db.execute(
            text("DELETE FROM empleados_empresa WHERE id = :id"),
            {"id": empleado_id}
        )
        db.commit()
        return {"mensaje": "Empleado eliminado correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════
# SECCIÓN: EXPORTACIONES
# ══════════════════════════════════════════

@router.get("/{empresa_id}/exportar-empleados")
def exportar_empleados(
    empresa_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        empresa = db.execute(
            text("SELECT razon_social FROM empresas WHERE id = :id"),
            {"id": empresa_id}
        ).fetchone()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        rows = db.execute(text("""
            SELECT nombre, apellido, dni, email, cargo,
                   activo, fecha_alta, fecha_baja
            FROM empleados_empresa
            WHERE empresa_id = :id
            ORDER BY fecha_alta DESC
        """), {"id": empresa_id}).fetchall()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Empleados"
        ws.append(["Nombre", "Apellido", "DNI", "Email", "Cargo",
                   "Estado", "Fecha Alta", "Fecha Baja"])

        for r in rows:
            ws.append([
                r.nombre, r.apellido, r.dni or "", r.email, r.cargo or "",
                "Activo" if r.activo else "Inactivo",
                r.fecha_alta.isoformat() if r.fecha_alta else "",
                r.fecha_baja.isoformat() if r.fecha_baja else "",
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        razon = empresa.razon_social.replace(" ", "_")[:30]
        fecha = date.today().isoformat()
        return Response(
            content=buffer.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=empleados_{razon}_{fecha}.xlsx"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Exportar todas las empresas ───────────────────────────────────────────────

@router.get("/exportar-empresas")
def exportar_empresas(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
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
        ws.append(["Razón Social", "CUIT", "Empleados activos", "Plan",
                   "Estado suscripción", "Próximo cobro", "Monto mensual"])

        for r in rows:
            ws.append([
                r.razon_social, r.cuit, r.empleados_activos or 0,
                r.plan_nombre or "", r.estado_suscripcion or "",
                r.proximo_cobro.isoformat() if r.proximo_cobro else "",
                float(r.precio_total) if r.precio_total else 0,
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        fecha = date.today().isoformat()
        return Response(
            content=buffer.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=empresas_{fecha}.xlsx"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Métricas empresariales ────────────────────────────────────────────────────

@router.get("/metricas-empresas")
def metricas_empresas(
    db: Session = Depends(get_db),
    _: int = Depends(require_admin)
):
    try:
        totales = db.execute(text("""
            SELECT
                COUNT(*) AS total_empresas,
                COUNT(*) FILTER (WHERE activo = true) AS empresas_activas
            FROM empresas
        """)).fetchone()

        empleados_activos = db.execute(text("""
            SELECT COUNT(*) AS total FROM empleados_empresa WHERE activo = true
        """)).fetchone().total

        mrr = db.execute(text("""
            SELECT COALESCE(SUM(precio_total), 0) AS mrr
            FROM suscripciones_empresariales WHERE estado = 'activa'
        """)).fetchone().mrr

        vencen_semana = db.execute(text("""
            SELECT COUNT(*) AS total FROM suscripciones_empresariales
            WHERE estado NOT IN ('cancelada', 'vencida')
            AND proximo_cobro BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
        """)).fetchone().total

        pendiente_pago = db.execute(text("""
            SELECT COUNT(*) AS total FROM suscripciones_empresariales
            WHERE estado = 'pendiente_pago'
        """)).fetchone().total

        return {
            "total_empresas": totales.total_empresas,
            "empresas_activas": totales.empresas_activas,
            "total_empleados_activos": empleados_activos,
            "mrr_empresarial": float(mrr),
            "empresas_vencen_esta_semana": vencen_semana,
            "empresas_pendiente_pago": pendiente_pago,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
