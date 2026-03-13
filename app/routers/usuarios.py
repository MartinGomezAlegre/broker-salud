from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schemas.usuario import UsuarioCrear, UsuarioRespuesta

router = APIRouter(
    prefix="/usuarios",
    tags=["usuarios"]
)

@router.post("/", response_model=UsuarioRespuesta)
def crear_usuario(usuario: UsuarioCrear, db: Session = Depends(get_db)):
    # Verificar si el email ya existe
    existe = db.execute(
        text("SELECT id FROM usuarios WHERE email = :email"),
        {"email": usuario.email}
    ).fetchone()

    if existe:
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    # Insertar el usuario
    db.execute(
        text("""INSERT INTO usuarios (nombre, apellido, email, telefono, fecha_nacimiento, password_hash)
           VALUES (:nombre, :apellido, :email, :telefono, :fecha_nacimiento, :password_hash)"""),
        {
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "email": usuario.email,
            "telefono": usuario.telefono,
            "fecha_nacimiento": usuario.fecha_nacimiento,
            "password_hash": usuario.contrasenia
        }
    )
    db.commit()

    # Devolver el usuario creado
    nuevo = db.execute(
        text("SELECT * FROM usuarios WHERE email = :email"),
        {"email": usuario.email}
    ).fetchone()

    return nuevo

@router.get("/{id}", response_model=UsuarioRespuesta)
def obtener_usuario(id: int, db: Session = Depends(get_db)):
    usuario = db.execute(
        text("SELECT * FROM usuarios WHERE id = :id"),
        {"id": id}
    ).fetchone()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return usuario