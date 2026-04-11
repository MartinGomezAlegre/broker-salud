from datetime import datetime, timezone
import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.credenciales import ValidacionBeneficio
from app.services.credenciales.common import (
    decode_qr_token,
    discount_percentage_for,
    log_validation,
    numero_socio,
)
from app.services.suscripciones.common import ensure_fecha_vencimiento

logger = logging.getLogger(__name__)


def validar_beneficio_token(
    db: Session,
    token: str,
    source_ip: str | None,
    user_agent: str | None,
) -> ValidacionBeneficio:
    checked_at = datetime.now(timezone.utc).isoformat()

    payload = decode_qr_token(token)
    if not payload:
        log_validation(db, None, "desconocido", False, source_ip, user_agent)
        return ValidacionBeneficio(
            valido=False,
            motivo="QR invalido o vencido",
            checked_at=checked_at,
        )

    usuario_id = int(payload.get("sub", 0))
    benefit_type = payload.get("benefit_type", "farmacia")

    try:
        ensure_fecha_vencimiento(db)
        row = db.execute(text("""
            SELECT u.id, u.nombre, u.apellido, p.nombre AS plan_nombre
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

        if not row:
            log_validation(db, usuario_id, benefit_type, False, source_ip, user_agent)
            return ValidacionBeneficio(
                valido=False,
                motivo="Afiliado sin cobertura vigente",
                checked_at=checked_at,
            )

        log_validation(db, usuario_id, benefit_type, True, source_ip, user_agent)
        return ValidacionBeneficio(
            valido=True,
            nombre_completo=f"{row.nombre} {row.apellido}".strip(),
            numero_socio=numero_socio(row.id),
            plan_nombre=row.plan_nombre,
            benefit_type=benefit_type,
            discount_percentage=discount_percentage_for(benefit_type),
            checked_at=checked_at,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en validar_beneficio_token: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
