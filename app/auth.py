from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY no está configurada en las variables de entorno. "
        "Generá una segura con: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
ALGORITHM = "HS256"
EXPIRACION_MINUTOS = 10080  # 7 días

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hashear_password(password: str) -> str:
    return pwd_context.hash(password)

def verificar_password(password: str, hash: str) -> bool:
    return pwd_context.verify(password, hash)

def crear_token(data: dict) -> str:
    datos = data.copy()
    expira = datetime.utcnow() + timedelta(minutes=EXPIRACION_MINUTOS)
    datos.update({"exp": expira})
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = payload.get("id")
        if usuario_id is None:
            return None
        return usuario_id
    except JWTError:
        return None


from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    usuario_id = verificar_token(token)
    if usuario_id is None:
        raise HTTPException(
            status_code=401,
            detail="Token inválido o expirado"
        )
    usuario = db.execute(
        text("SELECT activo FROM usuarios WHERE id = :id"),
        {"id": usuario_id}
    ).fetchone()
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=401,
            detail="Cuenta desactivada"
        )
    return usuario_id