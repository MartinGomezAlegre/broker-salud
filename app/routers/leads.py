import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.database import get_db
from app.auth import get_current_user
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/leads",
    tags=["leads"]
)

admin_router = APIRouter(
    prefix="/admin/leads",
    tags=["admin-leads"]
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class LeadEmpresarialCrear(BaseModel):
    razon_social: Optional[str] = None
    nombre_contacto: str
    email: EmailStr
    telefono: str
    cantidad_empleados: Optional[int] = None
    mensaje: Optional[str] = None


class LeadEmpresarialActualizar(BaseModel):
    estado: Optional[str] = None
    nota_admin: Optional[str] = None


# ── require_admin local ────────────────────────────────────────────────────────

def _require_admin_dep(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    from app.routers.admin import require_admin
    return require_admin(db=db, usuario_id=usuario_id)


# ── Endpoint público ───────────────────────────────────────────────────────────

@router.post("/empresarial")
@limiter.limit("3/hour")
def crear_lead_empresarial(
    request: Request,
    datos: LeadEmpresarialCrear,
    db: Session = Depends(get_db)
):
    try:
        db.execute(
            text("""
                INSERT INTO leads_empresariales
                    (razon_social, nombre_contacto, email, telefono, cantidad_empleados, mensaje)
                VALUES
                    (:razon_social, :nombre_contacto, :email, :telefono, :cantidad_empleados, :mensaje)
            """),
            {
                "razon_social": datos.razon_social,
                "nombre_contacto": datos.nombre_contacto,
                "email": str(datos.email),
                "telefono": datos.telefono,
                "cantidad_empleados": datos.cantidad_empleados,
                "mensaje": datos.mensaje,
            }
        )
        db.commit()

        try:
            from app.services.email import enviar_email_lead_empresarial
            enviar_email_lead_empresarial(
                datos.nombre_contacto,
                datos.razon_social,
                str(datos.email),
                datos.telefono,
                datos.cantidad_empleados,
                datos.mensaje,
            )
        except Exception as e:
            logger.error("Error enviando email lead empresarial: %s", e)

        return {"message": "Gracias por tu interés. Te contactamos en 24hs."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en crear_lead_empresarial: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# ── Endpoints de admin ─────────────────────────────────────────────────────────

@admin_router.get("/empresariales")
def listar_leads(
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(_require_admin_dep)
):
    try:
        params: dict = {}
        where = ""
        if estado:
            where = "WHERE estado = :estado"
            params["estado"] = estado

        leads = db.execute(text(f"""
            SELECT id, razon_social, nombre_contacto, email, telefono,
                   cantidad_empleados, mensaje, estado, nota_admin, created_at
            FROM leads_empresariales
            {where}
            ORDER BY created_at DESC
        """), params).fetchall()

        return [
            {
                "id": l.id,
                "razon_social": l.razon_social,
                "nombre_contacto": l.nombre_contacto,
                "email": l.email,
                "telefono": l.telefono,
                "cantidad_empleados": l.cantidad_empleados,
                "mensaje": l.mensaje,
                "estado": l.estado,
                "nota_admin": l.nota_admin,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en listar_leads: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@admin_router.put("/empresariales/{lead_id}")
def actualizar_lead(
    lead_id: int,
    datos: LeadEmpresarialActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(_require_admin_dep)
):
    try:
        lead = db.execute(
            text("SELECT id FROM leads_empresariales WHERE id = :id"),
            {"id": lead_id}
        ).fetchone()

        if not lead:
            raise HTTPException(status_code=404, detail="Lead no encontrado")

        campos = []
        params: dict = {"id": lead_id}

        if datos.estado is not None:
            campos.append("estado = :estado")
            params["estado"] = datos.estado
        if datos.nota_admin is not None:
            campos.append("nota_admin = :nota_admin")
            params["nota_admin"] = datos.nota_admin

        if not campos:
            raise HTTPException(status_code=400, detail="No se enviaron campos a actualizar")

        db.execute(
            text(f"UPDATE leads_empresariales SET {', '.join(campos)} WHERE id = :id"),
            params
        )
        db.commit()

        actualizado = db.execute(
            text("SELECT * FROM leads_empresariales WHERE id = :id"),
            {"id": lead_id}
        ).fetchone()

        return {
            "id": actualizado.id,
            "estado": actualizado.estado,
            "nota_admin": actualizado.nota_admin,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en actualizar_lead: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
