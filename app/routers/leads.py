import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.routers.admin_common import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/leads",
    tags=["leads"],
)

admin_router = APIRouter(
    prefix="/admin/leads",
    tags=["admin-leads"],
)


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


@router.post("/empresarial")
@limiter.limit("3/hour")
def crear_lead_empresarial(
    request: Request,
    response: Response,
    datos: LeadEmpresarialCrear,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    del request
    try:
        db.execute(text("""
            INSERT INTO leads_empresariales
                (razon_social, nombre_contacto, email, telefono, cantidad_empleados, mensaje)
            VALUES
                (:razon_social, :nombre_contacto, :email, :telefono, :cantidad_empleados, :mensaje)
        """), {
            "razon_social": datos.razon_social,
            "nombre_contacto": datos.nombre_contacto,
            "email": str(datos.email),
            "telefono": datos.telefono,
            "cantidad_empleados": datos.cantidad_empleados,
            "mensaje": datos.mensaje,
        })
        db.commit()

        from app.services.email import dispatch_email, enviar_email_lead_empresarial

        dispatch_email(
            background_tasks,
            enviar_email_lead_empresarial,
            datos.nombre_contacto,
            datos.razon_social,
            str(datos.email),
            datos.telefono,
            datos.cantidad_empleados,
            datos.mensaje,
        )

        return {"message": "Gracias por tu interes. Te contactamos en 24hs."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_lead_empresarial: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@admin_router.get("/empresariales")
def listar_leads(
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
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
                "id": lead.id,
                "razon_social": lead.razon_social,
                "nombre_contacto": lead.nombre_contacto,
                "email": lead.email,
                "telefono": lead.telefono,
                "cantidad_empleados": lead.cantidad_empleados,
                "mensaje": lead.mensaje,
                "estado": lead.estado,
                "nota_admin": lead.nota_admin,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            }
            for lead in leads
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_leads: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@admin_router.put("/empresariales/{lead_id}")
def actualizar_lead(
    lead_id: int,
    datos: LeadEmpresarialActualizar,
    db: Session = Depends(get_db),
    _: int = Depends(require_admin),
):
    try:
        lead = db.execute(
            text("SELECT id FROM leads_empresariales WHERE id = :id"),
            {"id": lead_id},
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
            params,
        )
        db.commit()

        actualizado = db.execute(
            text("SELECT id, estado, nota_admin FROM leads_empresariales WHERE id = :id"),
            {"id": lead_id},
        ).fetchone()

        return {
            "id": actualizado.id,
            "estado": actualizado.estado,
            "nota_admin": actualizado.nota_admin,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en actualizar_lead: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
