from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.auth import verificar_password, crear_token
from pydantic import BaseModel

router = APIRouter(
    prefix="/auth",
    tags=["autenticacion"]
)

class LoginData(BaseModel):
    email: str
    contrasenia: str

@router.post("/login")
def login(datos: LoginData, db: Session = Depends(get_db)):
    # Buscar el usuario por email
    usuario = db.execute(
        text("SELECT * FROM usuarios WHERE email = :email"),
        {"email": datos.email}
    ).fetchone()

    # Si no existe o la contraseña es incorrecta
    if not usuario:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not verificar_password(datos.contrasenia, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # Generar el token
    token = crear_token({"id": usuario.id})

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "email": usuario.email
        }
    }