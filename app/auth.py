from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.security.passwords import validate_password_strength
from app.settings import get_settings

settings = get_settings()

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
EXPIRACION_MINUTOS = 10080  # 7 dias

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hashear_password(password: str) -> str:
    return pwd_context.hash(validate_password_strength(password))


def verificar_password(password: str, hash: str) -> bool:
    return pwd_context.verify(password, hash)


def crear_token(data: dict) -> str:
    datos = data.copy()
    expira = datetime.utcnow() + timedelta(minutes=EXPIRACION_MINUTOS)
    datos.update({"exp": expira})
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("id") is None:
            return None
        return payload
    except JWTError:
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    payload = verificar_token(token)
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Token invalido o expirado",
        )
    usuario_id = payload["id"]
    token_password_version = int(payload.get("pwdv", 1))
    usuario = db.execute(
        text("SELECT activo, COALESCE(password_version, 1) AS password_version FROM usuarios WHERE id = :id"),
        {"id": usuario_id},
    ).fetchone()
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=401,
            detail="Cuenta desactivada",
        )
    if int(usuario.password_version) != token_password_version:
        raise HTTPException(
            status_code=401,
            detail="La sesion ya no es valida. Volve a iniciar sesion.",
        )
    return usuario_id
