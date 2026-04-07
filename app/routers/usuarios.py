import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.schemas.usuario import UsuarioCrear, UsuarioRespuesta
from app.auth import hashear_password, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/usuarios",
    tags=["usuarios"]
)

@router.post("", response_model=UsuarioRespuesta)
def crear_usuario(usuario: UsuarioCrear, db: Session = Depends(get_db)):
    try:
        existe = db.execute(
            text("SELECT id FROM usuarios WHERE email = :email"),
            {"email": usuario.email}
        ).fetchone()

        if existe:
            raise HTTPException(status_code=400, detail="El email ya está registrado")

        db.execute(
            text("""INSERT INTO usuarios
                    (nombre, apellido, email, telefono, fecha_nacimiento, dni, cuit, direccion, password_hash, activo)
                    VALUES
                    (:nombre, :apellido, :email, :telefono, :fecha_nacimiento, :dni, :cuit, :direccion, :password_hash, true)"""),
            {
                "nombre": usuario.nombre,
                "apellido": usuario.apellido,
                "email": usuario.email,
                "telefono": usuario.telefono,
                "fecha_nacimiento": usuario.fecha_nacimiento,
                "dni": usuario.dni,
                "cuit": usuario.cuit,
                "direccion": usuario.direccion,
                "password_hash": hashear_password(usuario.contrasenia)
            }
        )
        db.commit()

        nuevo = db.execute(
            text("SELECT * FROM usuarios WHERE email = :email"),
            {"email": usuario.email}
        ).fetchone()

        try:
            from app.services.email import enviar_email_bienvenida
            enviar_email_bienvenida(nuevo.email, nuevo.nombre)
        except Exception as e:
            logger.error("Error enviando email bienvenida: %s", e)

        return nuevo
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en crear_usuario: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/me")
@router.get("/mi-perfil")  # alias para compatibilidad hacia atrás
def mi_perfil(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        usuario = db.execute(
            text("""SELECT id, nombre, apellido, email, telefono,
                           dni, fecha_nacimiento, cuit, direccion,
                           localidad, provincia, created_at
                    FROM usuarios WHERE id = :id"""),
            {"id": usuario_id}
        ).fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "telefono": usuario.telefono,
            "dni": usuario.dni,
            "fecha_nacimiento": usuario.fecha_nacimiento.isoformat()
                if usuario.fecha_nacimiento else None,
            "cuit": usuario.cuit,
            "direccion": usuario.direccion,
            "localidad": usuario.localidad,
            "provincia": usuario.provincia,
            "created_at": usuario.created_at.isoformat()
                if usuario.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en mi_perfil: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


class PerfilActualizar(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    dni: Optional[str] = None
    cuit: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None


@router.put("/me")
def actualizar_perfil(
    datos: PerfilActualizar,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        campos = []
        params: dict = {"id": usuario_id}

        if datos.nombre is not None:
            campos.append("nombre = :nombre")
            params["nombre"] = datos.nombre
        if datos.apellido is not None:
            campos.append("apellido = :apellido")
            params["apellido"] = datos.apellido
        if datos.telefono is not None:
            campos.append("telefono = :telefono")
            params["telefono"] = datos.telefono
        if datos.dni is not None:
            campos.append("dni = :dni")
            params["dni"] = datos.dni
        if datos.cuit is not None:
            campos.append("cuit = :cuit")
            params["cuit"] = datos.cuit
        if datos.direccion is not None:
            campos.append("direccion = :direccion")
            params["direccion"] = datos.direccion
        if datos.localidad is not None:
            campos.append("localidad = :localidad")
            params["localidad"] = datos.localidad
        if datos.provincia is not None:
            campos.append("provincia = :provincia")
            params["provincia"] = datos.provincia

        if campos:
            db.execute(
                text(f"UPDATE usuarios SET {', '.join(campos)} WHERE id = :id"),
                params
            )
            db.commit()

        usuario = db.execute(
            text("""SELECT id, nombre, apellido, email, telefono,
                           dni, fecha_nacimiento, cuit, direccion,
                           localidad, provincia, created_at
                    FROM usuarios WHERE id = :id"""),
            {"id": usuario_id}
        ).fetchone()

        return {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "telefono": usuario.telefono,
            "dni": usuario.dni,
            "fecha_nacimiento": usuario.fecha_nacimiento.isoformat()
                if usuario.fecha_nacimiento else None,
            "cuit": usuario.cuit,
            "direccion": usuario.direccion,
            "localidad": usuario.localidad,
            "provincia": usuario.provincia,
            "created_at": usuario.created_at.isoformat()
                if usuario.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en actualizar_perfil: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


@router.get("/{id}", response_model=UsuarioRespuesta)
def obtener_usuario(
    id: int,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    try:
        if id != usuario_id:
            raise HTTPException(status_code=403, detail="No tenés permiso para ver este perfil")

        usuario = db.execute(
            text("SELECT * FROM usuarios WHERE id = :id"),
            {"id": id}
        ).fetchone()

        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return usuario
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en obtener_usuario: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
