from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import crear_token, hashear_password
from app.security.passwords import validate_password_strength

INVITATION_TTL_HOURS = 72


def create_account_invitation(
    db: Session,
    *,
    user_id: int,
    email: str,
    full_name: str,
    role: str,
    invited_by_user_id: int | None = None,
    context_type: str | None = None,
    context_id: str | int | None = None,
) -> dict:
    db.execute(
        text(
            """
            UPDATE account_invitations
            SET accepted_at = NOW()
            WHERE user_id = :user_id
              AND accepted_at IS NULL
            """
        ),
        {"user_id": user_id},
    )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITATION_TTL_HOURS)

    row = db.execute(
        text(
            """
            INSERT INTO account_invitations (
                user_id,
                email,
                role,
                full_name,
                token,
                expires_at,
                invited_by_user_id,
                context_type,
                context_id
            )
            VALUES (
                :user_id,
                :email,
                :role,
                :full_name,
                :token,
                :expires_at,
                :invited_by_user_id,
                :context_type,
                :context_id
            )
            RETURNING id, token, expires_at
            """
        ),
        {
            "user_id": user_id,
            "email": email.strip().lower(),
            "role": role,
            "full_name": full_name,
            "token": token,
            "expires_at": expires_at,
            "invited_by_user_id": invited_by_user_id,
            "context_type": context_type,
            "context_id": str(context_id) if context_id is not None else None,
        },
    ).fetchone()

    return {
        "id": row.id,
        "token": row.token,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


def get_account_invitation(db: Session, token: str) -> dict:
    row = _fetch_invitation(db, token)
    return {
        "email": row.email,
        "role": row.role,
        "full_name": row.full_name,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "accepted": row.accepted_at is not None,
        "expired": row.expires_at <= datetime.now(timezone.utc),
    }


def accept_account_invitation(db: Session, token: str, password: str) -> dict:
    try:
        clean_password = validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    invitation = _fetch_invitation(db, token)
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=400, detail="La invitacion ya fue utilizada")
    if invitation.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="La invitacion esta vencida")

    password_hash = hashear_password(clean_password)

    db.execute(
        text(
            """
            UPDATE usuarios
            SET password_hash = :password_hash,
                password_version = COALESCE(password_version, 1) + 1,
                activo = true
            WHERE id = :user_id
            """
        ),
        {"password_hash": password_hash, "user_id": invitation.user_id},
    )
    db.execute(
        text("UPDATE account_invitations SET accepted_at = NOW() WHERE id = :id"),
        {"id": invitation.id},
    )
    db.commit()

    user = db.execute(
        text(
            """
            SELECT id, nombre, email, rol, COALESCE(password_version, 1) AS password_version
            FROM usuarios
            WHERE id = :id
            """
        ),
        {"id": invitation.user_id},
    ).fetchone()

    access_token = crear_token({
        "id": user.id,
        "rol": user.rol,
        "pwdv": int(user.password_version or 1),
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario": {
            "id": user.id,
            "nombre": user.nombre,
            "email": user.email,
            "rol": user.rol,
        },
    }


def _fetch_invitation(db: Session, token: str):
    row = db.execute(
        text(
            """
            SELECT
                id,
                user_id,
                email,
                role,
                full_name,
                token,
                expires_at,
                accepted_at
            FROM account_invitations
            WHERE token = :token
            """
        ),
        {"token": token},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Invitacion no encontrada")

    return row
