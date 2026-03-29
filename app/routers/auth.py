import logging
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from app.database import get_db
from app.auth import verificar_password, crear_token, hashear_password
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["autenticacion"]
)


class LoginData(BaseModel):
    email: str
    contrasenia: str


class RecuperarContraseniaData(BaseModel):
    email: str


class NuevaContraseniaData(BaseModel):
    token: str
    nueva_contrasenia: str


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, datos: LoginData, db: Session = Depends(get_db)):
    try:
        usuario = db.execute(
            text("SELECT * FROM usuarios WHERE email = :email"),
            {"email": datos.email}
        ).fetchone()

        if not usuario:
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        if not verificar_password(datos.contrasenia, usuario.password_hash):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        token = crear_token({"id": usuario.id})

        return {
            "access_token": token,
            "token_type": "bearer",
            "usuario": {
                "id": usuario.id,
                "nombre": usuario.nombre,
                "email": usuario.email,
                "rol": usuario.rol
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en login: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("/recuperar-contrasenia")
@limiter.limit("3/hour")
def recuperar_contrasenia(
    request: Request,
    datos: RecuperarContraseniaData,
    db: Session = Depends(get_db)
):
    try:
        usuario = db.execute(
            text("SELECT id, nombre, email FROM usuarios WHERE email = :email"),
            {"email": datos.email}
        ).fetchone()

        # Respuesta siempre igual para no revelar si el email existe
        respuesta = {"message": "Si el email existe, te enviamos las instrucciones"}

        if not usuario:
            return respuesta

        token = secrets.token_urlsafe(32)
        expira_en = datetime.now(timezone.utc) + timedelta(hours=1)

        # Limpiar tokens anteriores no usados del mismo usuario
        db.execute(
            text("DELETE FROM tokens_recuperacion WHERE usuario_id = :uid AND usado = false"),
            {"uid": usuario.id}
        )

        db.execute(
            text("""
                INSERT INTO tokens_recuperacion (usuario_id, token, expira_en)
                VALUES (:usuario_id, :token, :expira_en)
            """),
            {"usuario_id": usuario.id, "token": token, "expira_en": expira_en}
        )
        db.commit()

        try:
            from app.services.email import enviar_email_recuperacion
            enviar_email_recuperacion(usuario.email, usuario.nombre, token)
        except Exception as e:
            logger.error("Error enviando email recuperacion: %s", e)

        return respuesta
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en recuperar_contrasenia: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("/nueva-contrasenia")
def nueva_contrasenia(datos: NuevaContraseniaData, db: Session = Depends(get_db)):
    try:
        if len(datos.nueva_contrasenia) < 8:
            raise HTTPException(
                status_code=400,
                detail="La contraseña debe tener al menos 8 caracteres"
            )

        registro = db.execute(
            text("""
                SELECT id, usuario_id FROM tokens_recuperacion
                WHERE token = :token
                  AND usado = false
                  AND expira_en > NOW()
            """),
            {"token": datos.token}
        ).fetchone()

        if not registro:
            raise HTTPException(status_code=400, detail="Token inválido o expirado")

        nuevo_hash = hashear_password(datos.nueva_contrasenia)

        db.execute(
            text("UPDATE usuarios SET password_hash = :hash WHERE id = :id"),
            {"hash": nuevo_hash, "id": registro.usuario_id}
        )
        db.execute(
            text("UPDATE tokens_recuperacion SET usado = true WHERE id = :id"),
            {"id": registro.id}
        )
        db.commit()

        return {"message": "Contraseña actualizada correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en nueva_contrasenia: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
