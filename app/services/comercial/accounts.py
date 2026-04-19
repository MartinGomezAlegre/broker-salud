import secrets

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import hashear_password
from app.security.passwords import validate_password_strength


def create_commercial_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    role: str,
) -> int:
    try:
        clean_password = validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = db.execute(
        text("SELECT id FROM usuarios WHERE LOWER(email) = LOWER(:email)"),
        {"email": email.strip()},
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    nombre, apellido = _split_name(full_name)

    row = db.execute(
        text(
            """
            INSERT INTO usuarios (
                nombre,
                apellido,
                email,
                telefono,
                fecha_nacimiento,
                dni,
                cuit,
                direccion,
                localidad,
                codigo_postal,
                provincia,
                pais,
                password_hash,
                activo,
                rol
            )
            VALUES (
                :nombre,
                :apellido,
                :email,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                :password_hash,
                true,
                :rol
            )
            RETURNING id
            """
        ),
        {
            "nombre": nombre,
            "apellido": apellido,
            "email": email.strip().lower(),
            "password_hash": hashear_password(clean_password),
            "rol": role,
        },
    ).fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="No pudimos crear la cuenta comercial")

    return row.id


def create_pending_commercial_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    role: str,
) -> int:
    existing = db.execute(
        text("SELECT id FROM usuarios WHERE LOWER(email) = LOWER(:email)"),
        {"email": email.strip()},
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    nombre, apellido = _split_name(full_name)
    provisional_password = f"Invita{secrets.token_urlsafe(16)}1"

    row = db.execute(
        text(
            """
            INSERT INTO usuarios (
                nombre,
                apellido,
                email,
                telefono,
                fecha_nacimiento,
                dni,
                cuit,
                direccion,
                localidad,
                codigo_postal,
                provincia,
                pais,
                password_hash,
                activo,
                rol,
                password_version
            )
            VALUES (
                :nombre,
                :apellido,
                :email,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                :password_hash,
                false,
                :rol,
                0
            )
            RETURNING id
            """
        ),
        {
            "nombre": nombre,
            "apellido": apellido,
            "email": email.strip().lower(),
            "password_hash": hashear_password(provisional_password),
            "rol": role,
        },
    ).fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="No pudimos preparar la cuenta comercial")

    return row.id


def update_commercial_user(
    db: Session,
    *,
    usuario_id: int,
    full_name: str,
    email: str,
    role: str,
    password: str | None = None,
):
    user = db.execute(
        text("SELECT id FROM usuarios WHERE id = :id"),
        {"id": usuario_id},
    ).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario comercial no encontrado")

    existing = db.execute(
        text("SELECT id FROM usuarios WHERE LOWER(email) = LOWER(:email) AND id <> :id"),
        {"email": email.strip(), "id": usuario_id},
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe otro usuario con ese email")

    nombre, apellido = _split_name(full_name)
    params: dict[str, object] = {
        "id": usuario_id,
        "nombre": nombre,
        "apellido": apellido,
        "email": email.strip().lower(),
        "rol": role,
    }

    set_parts = [
        "nombre = :nombre",
        "apellido = :apellido",
        "email = :email",
        "rol = :rol",
    ]

    if password and password.strip():
        try:
            clean_password = validate_password_strength(password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        params["password_hash"] = hashear_password(clean_password)
        set_parts.append("password_hash = :password_hash")
        set_parts.append("password_version = COALESCE(password_version, 1) + 1")

    db.execute(
        text(f"UPDATE usuarios SET {', '.join(set_parts)} WHERE id = :id"),
        params,
    )


def _split_name(full_name: str) -> tuple[str, str]:
    clean = " ".join((full_name or "").strip().split())
    if not clean:
        return "Comercial", ""
    parts = clean.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""
