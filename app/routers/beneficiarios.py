import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/beneficiarios", tags=["beneficiarios"])


class BeneficiarioCrear(BaseModel):
    nombre: str
    apellido: str
    dni: str
    fecha_nacimiento: date
    relacion: str


def _max_adicionales(tipo_plan: str | None, max_beneficiarios: int | None) -> int:
    tipo = (tipo_plan or "").lower()
    total = max_beneficiarios or 0
    if tipo == "familiar":
        total = min(total, 4)
    return max(total - 1, 0)


@router.get("")
def listar_beneficiarios(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        suscripcion = db.execute(
            text(
                """
                SELECT id
                FROM suscripciones
                WHERE usuario_id = :usuario_id
                  AND estado IN ('activa', 'cancelacion_programada')
                ORDER BY COALESCE(fecha_vencimiento, created_at) DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id},
        ).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenes una suscripcion activa")

        beneficiarios = db.execute(
            text(
                """
                SELECT id, nombre, apellido, dni, fecha_nacimiento, relacion
                FROM beneficiarios
                WHERE suscripcion_id = :suscripcion_id
                ORDER BY created_at ASC
                """
            ),
            {"suscripcion_id": suscripcion.id},
        ).fetchall()

        return [
            {
                "id": item.id,
                "nombre": item.nombre,
                "apellido": item.apellido,
                "dni": item.dni,
                "fecha_nacimiento": item.fecha_nacimiento.isoformat() if item.fecha_nacimiento else None,
                "relacion": item.relacion,
            }
            for item in beneficiarios
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_beneficiarios: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("")
@limiter.limit("20/day")
def agregar_beneficiario(
    request: Request,
    response: Response,
    datos: BeneficiarioCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        suscripcion = db.execute(
            text(
                """
                SELECT s.id, p.max_beneficiarios, p.tipo
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                WHERE s.usuario_id = :usuario_id
                  AND s.estado IN ('activa', 'cancelacion_programada')
                ORDER BY COALESCE(s.fecha_vencimiento, s.created_at) DESC, s.created_at DESC
                LIMIT 1
                """
            ),
            {"usuario_id": usuario_id},
        ).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenes una suscripcion activa")

        cupo_adicional = _max_adicionales(suscripcion.tipo, suscripcion.max_beneficiarios)
        if cupo_adicional <= 0 or (suscripcion.tipo and suscripcion.tipo.lower() == "personal"):
            raise HTTPException(status_code=400, detail="Tu plan no admite beneficiarios adicionales")

        cantidad_actual = db.execute(
            text("SELECT COUNT(*) AS cnt FROM beneficiarios WHERE suscripcion_id = :sid"),
            {"sid": suscripcion.id},
        ).fetchone().cnt

        if cantidad_actual >= cupo_adicional:
            raise HTTPException(status_code=400, detail="Ya alcanzaste el limite de integrantes permitidos")

        nuevo = db.execute(
            text(
                """
                INSERT INTO beneficiarios
                    (suscripcion_id, nombre, apellido, dni, fecha_nacimiento, relacion)
                VALUES
                    (:suscripcion_id, :nombre, :apellido, :dni, :fecha_nacimiento, :relacion)
                RETURNING id, nombre, apellido, dni, fecha_nacimiento, relacion
                """
            ),
            {
                "suscripcion_id": suscripcion.id,
                "nombre": datos.nombre,
                "apellido": datos.apellido,
                "dni": datos.dni,
                "fecha_nacimiento": datos.fecha_nacimiento,
                "relacion": datos.relacion,
            },
        ).fetchone()
        db.commit()

        return {
            "id": nuevo.id,
            "nombre": nuevo.nombre,
            "apellido": nuevo.apellido,
            "dni": nuevo.dni,
            "fecha_nacimiento": nuevo.fecha_nacimiento.isoformat() if nuevo.fecha_nacimiento else None,
            "relacion": nuevo.relacion,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en agregar_beneficiario: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.delete("/{beneficiario_id}")
def eliminar_beneficiario(
    beneficiario_id: int,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        beneficiario = db.execute(
            text(
                """
                SELECT b.id
                FROM beneficiarios b
                JOIN suscripciones s ON s.id = b.suscripcion_id
                WHERE b.id = :beneficiario_id AND s.usuario_id = :usuario_id
                """
            ),
            {"beneficiario_id": beneficiario_id, "usuario_id": usuario_id},
        ).fetchone()

        if not beneficiario:
            raise HTTPException(status_code=403, detail="No tenes permiso para eliminar este beneficiario")

        db.execute(text("DELETE FROM beneficiarios WHERE id = :id"), {"id": beneficiario_id})
        db.commit()
        return {"message": "Beneficiario eliminado correctamente"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en eliminar_beneficiario: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
