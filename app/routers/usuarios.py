from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schemas.usuario import UsuarioCrear, UsuarioRespuesta
from app.auth import hashear_password, get_current_user

router = APIRouter(
    prefix="/usuarios",
    tags=["usuarios"]
)

@router.post("", response_model=UsuarioRespuesta)
def crear_usuario(usuario: UsuarioCrear, db: Session = Depends(get_db)):
    existe = db.execute(
        text("SELECT id FROM usuarios WHERE email = :email"),
        {"email": usuario.email}
    ).fetchone()

    if existe:
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    db.execute(
        text("""INSERT INTO usuarios
                (nombre, apellido, email, telefono, fecha_nacimiento, dni, password_hash, activo)
                VALUES
                (:nombre, :apellido, :email, :telefono, :fecha_nacimiento, :dni, :password_hash, true)"""),
        {
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "telefono": usuario.telefono,
            "fecha_nacimiento": usuario.fecha_nacimiento,
            "dni": usuario.dni,
            "password_hash": hashear_password(usuario.contrasenia)
        }
    )
    db.commit()

    nuevo = db.execute(
        text("SELECT * FROM usuarios WHERE email = :email"),
        {"email": usuario.email}
    ).fetchone()

    return nuevo


@router.get("/mi-perfil")
def mi_perfil(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user)
):
    usuario = db.execute(
        text("""SELECT id, nombre, apellido, email, telefono,
                       dni, fecha_nacimiento, created_at
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
        "created_at": usuario.created_at.isoformat()
            if usuario.created_at else None,
    }


@router.get("/{id}", response_model=UsuarioRespuesta)
def obtener_usuario(id: int, db: Session = Depends(get_db)):
    usuario = db.execute(
        text("SELECT * FROM usuarios WHERE id = :id"),
        {"id": id}
    ).fetchone()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return usuario