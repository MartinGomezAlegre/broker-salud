import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user, hashear_password
from app.database import get_db
from app.schemas.usuario import UsuarioCrear, UsuarioRespuesta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

DATOS_FACTURACION_REQUERIDOS = (
    "cuit",
    "direccion",
    "localidad",
    "codigo_postal",
    "provincia",
    "pais",
)


def _perfil_payload(usuario) -> dict:
    perfil = {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "email": usuario.email,
        "telefono": usuario.telefono,
        "dni": usuario.dni,
        "fecha_nacimiento": usuario.fecha_nacimiento.isoformat() if usuario.fecha_nacimiento else None,
        "cuit": usuario.cuit,
        "direccion": usuario.direccion,
        "localidad": usuario.localidad,
        "codigo_postal": usuario.codigo_postal,
        "provincia": usuario.provincia,
        "pais": usuario.pais,
        "created_at": usuario.created_at.isoformat() if usuario.created_at else None,
    }
    perfil["perfil_completo_facturacion"] = all(
        bool((perfil.get(field) or "").strip()) for field in DATOS_FACTURACION_REQUERIDOS
    )
    return perfil


@router.post("", response_model=UsuarioRespuesta)
def crear_usuario(usuario: UsuarioCrear, db: Session = Depends(get_db)):
    try:
        existe = db.execute(
            text("SELECT id FROM usuarios WHERE email = :email"),
            {"email": usuario.email},
        ).fetchone()

        if existe:
            raise HTTPException(status_code=400, detail="El email ya esta registrado")

        db.execute(
            text(
                """
                INSERT INTO usuarios
                    (nombre, apellido, email, telefono, fecha_nacimiento, dni,
                     cuit, direccion, localidad, codigo_postal, provincia, pais,
                     password_hash, activo)
                VALUES
                    (:nombre, :apellido, :email, :telefono, :fecha_nacimiento, :dni,
                     :cuit, :direccion, :localidad, :codigo_postal, :provincia, :pais,
                     :password_hash, true)
                """
            ),
            {
                "nombre": usuario.nombre,
                "apellido": usuario.apellido,
                "email": usuario.email,
                "telefono": usuario.telefono,
                "fecha_nacimiento": usuario.fecha_nacimiento,
                "dni": usuario.dni,
                "cuit": usuario.cuit,
                "direccion": usuario.direccion,
                "localidad": usuario.localidad,
                "codigo_postal": usuario.codigo_postal,
                "provincia": usuario.provincia,
                "pais": usuario.pais,
                "password_hash": hashear_password(usuario.contrasenia),
            },
        )
        db.commit()

        nuevo = db.execute(
            text("SELECT * FROM usuarios WHERE email = :email"),
            {"email": usuario.email},
        ).fetchone()

        try:
            from app.services.email import enviar_email_bienvenida

            enviar_email_bienvenida(nuevo.email, nuevo.nombre)
        except Exception as exc:  # pragma: no cover - side effect externo
            logger.error("Error enviando email bienvenida: %s", exc)

        return nuevo
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_usuario: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/me")
@router.get("/mi-perfil")
def mi_perfil(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        usuario = db.execute(
            text(
                """
                SELECT id, nombre, apellido, email, telefono,
                       dni, fecha_nacimiento, cuit, direccion,
                       localidad, codigo_postal, provincia, pais, created_at
                FROM usuarios
                WHERE id = :id
                """
            ),
            {"id": usuario_id},
        ).fetchone()

        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return _perfil_payload(usuario)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en mi_perfil: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


class PerfilActualizar(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    dni: Optional[str] = None
    cuit: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    codigo_postal: Optional[str] = None
    provincia: Optional[str] = None
    pais: Optional[str] = None


@router.put("/me")
def actualizar_perfil(
    datos: PerfilActualizar,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        campos = []
        params: dict = {"id": usuario_id}

        for campo, valor in datos.model_dump(exclude_none=True).items():
            campos.append(f"{campo} = :{campo}")
            params[campo] = valor.strip() if isinstance(valor, str) else valor

        if campos:
            db.execute(
                text(f"UPDATE usuarios SET {', '.join(campos)} WHERE id = :id"),
                params,
            )
            db.commit()

        usuario = db.execute(
            text(
                """
                SELECT id, nombre, apellido, email, telefono,
                       dni, fecha_nacimiento, cuit, direccion,
                       localidad, codigo_postal, provincia, pais, created_at
                FROM usuarios
                WHERE id = :id
                """
            ),
            {"id": usuario_id},
        ).fetchone()

        return _perfil_payload(usuario)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en actualizar_perfil: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/{id}", response_model=UsuarioRespuesta)
def obtener_usuario(
    id: int,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    try:
        if id != usuario_id:
            raise HTTPException(status_code=403, detail="No tenes permiso para ver este perfil")

        usuario = db.execute(
            text("SELECT * FROM usuarios WHERE id = :id"),
            {"id": id},
        ).fetchone()

        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return usuario
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en obtener_usuario: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
