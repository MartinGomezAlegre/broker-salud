from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
EXPIRACION_MINUTOS = 30

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