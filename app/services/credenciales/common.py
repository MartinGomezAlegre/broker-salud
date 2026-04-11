import base64
import io
import logging
import os
from datetime import datetime, timedelta, timezone

import qrcode
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import SECRET_KEY

logger = logging.getLogger(__name__)

QR_SECRET = os.getenv("QR_SECRET") or SECRET_KEY
QR_ALGORITHM = "HS256"
QR_TOKEN_SECONDS = int(os.getenv("QR_TOKEN_SECONDS", "60"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://celdoctor.com").rstrip("/")
DEFAULT_BENEFIT_TYPE = os.getenv("QR_DEFAULT_BENEFIT_TYPE", "farmacia")
DEFAULT_DISCOUNT_PERCENTAGE = int(os.getenv("FARMACIA_DESCUENTO_PORCENTAJE", "70"))
_qr_validations_table_checked = False
_qr_validations_table_available = False


def numero_socio(usuario_id: int) -> str:
    return f"CD-{usuario_id:08d}"


def discount_percentage_for(benefit_type: str) -> int:
    if benefit_type == "farmacia":
        return DEFAULT_DISCOUNT_PERCENTAGE
    env_name = f"{benefit_type.upper()}_DESCUENTO_PORCENTAJE"
    return int(os.getenv(env_name, str(DEFAULT_DISCOUNT_PERCENTAGE)))


def create_qr_token(
    usuario_id: int,
    benefit_type: str = DEFAULT_BENEFIT_TYPE,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=QR_TOKEN_SECONDS)
    payload = {
        "sub": str(usuario_id),
        "benefit_type": benefit_type,
        "iat": int(now.timestamp()),
        "exp": expires_at,
    }
    token = jwt.encode(payload, QR_SECRET, algorithm=QR_ALGORITHM)
    return token, expires_at


def decode_qr_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, QR_SECRET, algorithms=[QR_ALGORITHM])
        return payload
    except JWTError:
        return None


def validation_url(token: str) -> str:
    return f"{FRONTEND_URL}/validar/{token}"


def qr_image_data_url(url: str) -> str:
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def log_validation(
    db: Session,
    usuario_id: int | None,
    benefit_type: str,
    valido: bool,
    source_ip: str | None,
    user_agent: str | None,
):
    if not _ensure_qr_validations_table(db):
        return

    try:
        db.execute(text("""
            INSERT INTO qr_validations (
                user_id,
                benefit_type,
                validation_status,
                source_ip,
                user_agent,
                created_at
            )
            VALUES (
                :user_id,
                :benefit_type,
                :validation_status,
                :source_ip,
                :user_agent,
                NOW()
            )
        """), {
            "user_id": usuario_id,
            "benefit_type": benefit_type,
            "validation_status": "valido" if valido else "rechazado",
            "source_ip": source_ip,
            "user_agent": user_agent,
        })
        db.commit()
    except Exception as exc:
        logger.warning("No se pudo registrar qr_validation: %s", exc)
        db.rollback()


def _ensure_qr_validations_table(db: Session) -> bool:
    global _qr_validations_table_checked, _qr_validations_table_available
    if _qr_validations_table_checked:
        return _qr_validations_table_available

    row = db.execute(text("""
        SELECT to_regclass('public.qr_validations') AS tabla
    """)).fetchone()
    _qr_validations_table_available = bool(row and row.tabla)
    _qr_validations_table_checked = True
    return _qr_validations_table_available
