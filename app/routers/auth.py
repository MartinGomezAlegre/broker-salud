import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import crear_token, hashear_password, verificar_password
from app.database import get_db
from app.limiter import limiter
from app.security.passwords import validate_password_strength

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["autenticacion"],
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
def login(request: Request, response: Response, datos: LoginData, db: Session = Depends(get_db)):
    try:
        usuario = db.execute(
            text(
                """
                SELECT id, nombre, email, rol, activo, password_hash, COALESCE(password_version, 1) AS password_version
                FROM usuarios
                WHERE email = :email
                """
            ),
            {"email": datos.email},
        ).fetchone()

        if not usuario:
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        if not verificar_password(datos.contrasenia, usuario.password_hash):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        if not usuario.activo:
            raise HTTPException(status_code=401, detail="Cuenta desactivada")

        token = crear_token({
            "id": usuario.id,
            "rol": usuario.rol,
            "pwdv": int(usuario.password_version or 1),
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "usuario": {
                "id": usuario.id,
                "nombre": usuario.nombre,
                "email": usuario.email,
                "rol": usuario.rol,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en login: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("/recuperar-contrasenia")
@limiter.limit("3/hour")
def recuperar_contrasenia(
    request: Request,
    response: Response,
    datos: RecuperarContraseniaData,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        usuario = db.execute(
            text("SELECT id, nombre, email FROM usuarios WHERE email = :email"),
            {"email": datos.email},
        ).fetchone()

        respuesta = {"message": "Si el email existe, te enviamos las instrucciones"}

        if not usuario:
            return respuesta

        token = secrets.token_urlsafe(32)
        expira_en = datetime.now(timezone.utc) + timedelta(hours=1)

        db.execute(
            text("DELETE FROM tokens_recuperacion WHERE usuario_id = :uid AND usado = false"),
            {"uid": usuario.id},
        )

        db.execute(
            text(
                """
                INSERT INTO tokens_recuperacion (usuario_id, token, expira_en)
                VALUES (:usuario_id, :token, :expira_en)
                """
            ),
            {"usuario_id": usuario.id, "token": token, "expira_en": expira_en},
        )
        db.commit()

        from app.services.email import dispatch_email, enviar_email_recuperacion

        dispatch_email(background_tasks, enviar_email_recuperacion, usuario.email, usuario.nombre, token)

        return respuesta
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en recuperar_contrasenia: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.post("/nueva-contrasenia")
def nueva_contrasenia(datos: NuevaContraseniaData, db: Session = Depends(get_db)):
    try:
        try:
            nueva_contrasenia = validate_password_strength(datos.nueva_contrasenia)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        registro = db.execute(
            text(
                """
                SELECT id, usuario_id FROM tokens_recuperacion
                WHERE token = :token
                  AND usado = false
                  AND expira_en > NOW()
                """
            ),
            {"token": datos.token},
        ).fetchone()

        if not registro:
            raise HTTPException(status_code=400, detail="Token invalido o expirado")

        nuevo_hash = hashear_password(nueva_contrasenia)

        db.execute(
            text(
                """
                UPDATE usuarios
                SET password_hash = :hash,
                    password_version = COALESCE(password_version, 1) + 1
                WHERE id = :id
                """
            ),
            {"hash": nuevo_hash, "id": registro.usuario_id},
        )
        db.execute(
            text("UPDATE tokens_recuperacion SET usado = true WHERE id = :id"),
            {"id": registro.id},
        )
        db.commit()

        return {"message": "Contrasena actualizada correctamente"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en nueva_contrasenia: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
