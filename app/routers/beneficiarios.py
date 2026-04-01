import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import date
from app.database import get_db
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/beneficiarios",
    tags=["beneficiarios"]
)


class BeneficiarioCrear(BaseModel):
    nombre: str
    apellido: str
    dni: str
    fecha_nacimiento: date
    relacion: str


@router.get("")
def listar_beneficiarios(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        suscripcion = db.execute(
            text("""
                SELECT id FROM suscripciones
                WHERE usuario_id = :usuario_id AND estado = 'activa'
                ORDER BY created_at DESC LIMIT 1
            """),
            {"usuario_id": usuario_id}
        ).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenés una suscripción activa")

        beneficiarios = db.execute(
            text("""
                SELECT id, nombre, apellido, dni, fecha_nacimiento, relacion
                FROM beneficiarios
                WHERE suscripcion_id = :suscripcion_id
                ORDER BY created_at ASC
            """),
            {"suscripcion_id": suscripcion.id}
        ).fetchall()

        return [
            {
                "id": b.id,
                "nombre": b.nombre,
                "apellido": b.apellido,
                "dni": b.dni,
                "fecha_nacimiento": b.fecha_nacimiento.isoformat() if b.fecha_nacimiento else None,
                "relacion": b.relacion,
            }
            for b in beneficiarios
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en listar_beneficiarios: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("")
def agregar_beneficiario(
    datos: BeneficiarioCrear,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        suscripcion = db.execute(
            text("""
                SELECT s.id, p.max_beneficiarios, p.tipo
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                WHERE s.usuario_id = :usuario_id AND s.estado = 'activa'
                ORDER BY s.created_at DESC LIMIT 1
            """),
            {"usuario_id": usuario_id}
        ).fetchone()

        if not suscripcion:
            raise HTTPException(status_code=404, detail="No tenés una suscripción activa")

        max_benef = suscripcion.max_beneficiarios or 0
        cupo_adicional = max(max_benef - 1, 0)

        if cupo_adicional <= 0 or (suscripcion.tipo and suscripcion.tipo.lower() == "personal"):
            raise HTTPException(
                status_code=400,
                detail="Tu plan no admite beneficiarios adicionales"
            )

        cantidad_actual = db.execute(
            text("SELECT COUNT(*) as cnt FROM beneficiarios WHERE suscripcion_id = :sid"),
            {"sid": suscripcion.id}
        ).fetchone().cnt

        if cantidad_actual >= cupo_adicional:
            raise HTTPException(
                status_code=400,
                detail="Ya alcanzaste el límite de beneficiarios de tu plan"
            )

        nuevo = db.execute(
            text("""
                INSERT INTO beneficiarios
                    (suscripcion_id, nombre, apellido, dni, fecha_nacimiento, relacion)
                VALUES
                    (:suscripcion_id, :nombre, :apellido, :dni, :fecha_nacimiento, :relacion)
                RETURNING id, nombre, apellido, dni, fecha_nacimiento, relacion
            """),
            {
                "suscripcion_id": suscripcion.id,
                "nombre": datos.nombre,
                "apellido": datos.apellido,
                "dni": datos.dni,
                "fecha_nacimiento": datos.fecha_nacimiento,
                "relacion": datos.relacion,
            }
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
    except Exception as e:
        logger.error("Error en agregar_beneficiario: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.delete("/{beneficiario_id}")
def eliminar_beneficiario(
    beneficiario_id: int,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        # Verificar que el beneficiario pertenece a una suscripción del usuario
        beneficiario = db.execute(
            text("""
                SELECT b.id FROM beneficiarios b
                JOIN suscripciones s ON s.id = b.suscripcion_id
                WHERE b.id = :beneficiario_id AND s.usuario_id = :usuario_id
            """),
            {"beneficiario_id": beneficiario_id, "usuario_id": usuario_id}
        ).fetchone()

        if not beneficiario:
            raise HTTPException(status_code=403, detail="No tenés permiso para eliminar este beneficiario")

        db.execute(
            text("DELETE FROM beneficiarios WHERE id = :id"),
            {"id": beneficiario_id}
        )
        db.commit()

        return {"message": "Beneficiario eliminado correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en eliminar_beneficiario: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
