import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.credenciales import CredencialVirtual
from app.services.credenciales.common import (
    DEFAULT_BENEFIT_TYPE,
    create_qr_token,
    discount_percentage_for,
    numero_socio,
    qr_image_data_url,
    validation_url,
)
from app.services.suscripciones.common import ensure_fecha_vencimiento

logger = logging.getLogger(__name__)


def obtener_credencial_virtual(
    db: Session,
    usuario_id: int,
) -> CredencialVirtual:
    try:
        ensure_fecha_vencimiento(db)
        usuario = db.execute(text("""
            SELECT u.id, u.nombre, u.apellido, u.dni, p.nombre AS plan_nombre
            FROM usuarios u
            JOIN suscripciones s ON s.usuario_id = u.id
            JOIN planes p ON p.id = s.plan_id
            WHERE u.id = :usuario_id
              AND u.activo = true
              AND s.estado IN ('activa', 'cancelacion_programada')
              AND (s.fecha_vencimiento IS NULL OR s.fecha_vencimiento >= CURRENT_DATE)
            ORDER BY COALESCE(s.fecha_vencimiento, s.created_at) DESC, s.created_at DESC
            LIMIT 1
        """), {"usuario_id": usuario_id}).fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="No encontramos una credencial activa para tu cuenta")

        token, expires_at = create_qr_token(usuario_id, DEFAULT_BENEFIT_TYPE)
        url = validation_url(token)
        return CredencialVirtual(
            nombre_completo=f"{usuario.nombre} {usuario.apellido}".strip(),
            dni=usuario.dni,
            numero_socio=numero_socio(usuario.id),
            plan_nombre=usuario.plan_nombre,
            benefit_type=DEFAULT_BENEFIT_TYPE,
            discount_percentage=discount_percentage_for(DEFAULT_BENEFIT_TYPE),
            qr_token=token,
            qr_expires_at=expires_at.isoformat(),
            validation_url=url,
            qr_image_data_url=qr_image_data_url(url),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en obtener_credencial_virtual: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
