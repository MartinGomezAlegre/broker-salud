import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.comercial.accounts import (
    create_commercial_user,
    create_pending_commercial_user,
    update_commercial_user,
)
from app.services.comercial.common import ensure_commercial_schema, generate_referral_code, referral_code_exists
from app.services.email import dispatch_email, enviar_email_invitacion_cuenta
from app.services.invitations import create_account_invitation

logger = logging.getLogger(__name__)


def listar_mi_equipo_broker(db: Session, usuario_id: int):
    broker = _resolve_broker(db, usuario_id)
    rows = db.execute(
        text(
            """
            SELECT
                bs.id,
                bs.nombre,
                bs.email,
                bs.referral_code,
                bs.estado,
                bs.fecha_alta,
                bs.usuario_id
            FROM broker_sellers bs
            WHERE bs.broker_id = :broker_id
            ORDER BY bs.fecha_alta DESC, bs.id DESC
            """
        ),
        {"broker_id": broker.id},
    ).fetchall()

    return [_serialize_team_member(row) for row in rows]


def crear_broker_seller_desde_broker(
    db: Session,
    usuario_id: int,
    *,
    nombre: str,
    email: str,
    contrasenia: str | None,
    referral_code: str | None,
    estado: str,
):
    try:
        ensure_commercial_schema(db)
        broker = _resolve_broker(db, usuario_id)
        code = referral_code or generate_referral_code(db, nombre)
        if referral_code_exists(db, code):
            raise HTTPException(status_code=400, detail="El referral code ya esta en uso")

        invitation_email = None
        if contrasenia and contrasenia.strip():
            linked_user_id = create_commercial_user(
                db,
                full_name=nombre,
                email=email,
                password=contrasenia,
                role="broker_seller",
            )
        else:
            linked_user_id = create_pending_commercial_user(
                db,
                full_name=nombre,
                email=email,
                role="broker_seller",
            )
            invitation = create_account_invitation(
                db,
                user_id=linked_user_id,
                email=email,
                full_name=nombre,
                role="broker_seller",
                invited_by_user_id=usuario_id,
                context_type="broker_seller",
                context_id=broker.id,
            )
            invitation_email = {
                "email": email,
                "full_name": nombre,
                "token": invitation["token"],
                "role": "broker_seller",
            }

        row = db.execute(
            text(
                """
                INSERT INTO broker_sellers (
                    broker_id,
                    nombre,
                    email,
                    referral_code,
                    estado,
                    fecha_alta,
                    usuario_id
                )
                VALUES (
                    :broker_id,
                    :nombre,
                    :email,
                    :referral_code,
                    :estado,
                    NOW(),
                    :usuario_id
                )
                RETURNING id
                """
            ),
            {
                "broker_id": broker.id,
                "nombre": nombre,
                "email": email.strip().lower(),
                "referral_code": code,
                "estado": estado,
                "usuario_id": linked_user_id,
            },
        ).fetchone()

        db.commit()
        if invitation_email:
            dispatch_email(
                None,
                enviar_email_invitacion_cuenta,
                invitation_email["email"],
                invitation_email["full_name"],
                invitation_email["token"],
                invitation_email["role"],
            )
        return obtener_miembro_equipo(db, usuario_id, row.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_broker_seller_desde_broker: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos crear el vendedor del broker")


def actualizar_broker_seller_desde_broker(
    db: Session,
    usuario_id: int,
    seller_id: int,
    *,
    nombre: str | None,
    email: str | None,
    nueva_contrasenia: str | None,
    referral_code: str | None,
    estado: str | None,
):
    try:
        ensure_commercial_schema(db)
        broker = _resolve_broker(db, usuario_id)
        actual = db.execute(
            text(
                """
                SELECT id, broker_id, nombre, email, referral_code, usuario_id
                FROM broker_sellers
                WHERE id = :id
                """
            ),
            {"id": seller_id},
        ).fetchone()

        if not actual or actual.broker_id != broker.id:
            raise HTTPException(status_code=404, detail="Vendedor no encontrado en tu equipo")

        payload: dict[str, object] = {}
        next_name = nombre or actual.nombre
        next_email = (email or actual.email).strip().lower()

        if referral_code is not None:
            code = referral_code or generate_referral_code(db, next_name)
            if referral_code_exists(db, code, exclude_table="broker_sellers", exclude_id=seller_id):
                raise HTTPException(status_code=400, detail="El referral code ya esta en uso")
            payload["referral_code"] = code

        if nombre is not None:
            payload["nombre"] = nombre
        if email is not None:
            payload["email"] = next_email
        if estado is not None:
            payload["estado"] = estado

        if actual.usuario_id:
            update_commercial_user(
                db,
                usuario_id=actual.usuario_id,
                full_name=next_name,
                email=next_email,
                password=nueva_contrasenia,
                role="broker_seller",
            )

        if payload:
            set_clause = ", ".join(f"{field} = :{field}" for field in payload)
            db.execute(
                text(f"UPDATE broker_sellers SET {set_clause} WHERE id = :id"),
                {"id": seller_id, **payload},
            )

        db.commit()
        return obtener_miembro_equipo(db, usuario_id, seller_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en actualizar_broker_seller_desde_broker: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos actualizar el vendedor del broker")


def obtener_miembro_equipo(db: Session, usuario_id: int, seller_id: int):
    broker = _resolve_broker(db, usuario_id)
    row = db.execute(
        text(
            """
            SELECT
                bs.id,
                bs.nombre,
                bs.email,
                bs.referral_code,
                bs.estado,
                bs.fecha_alta,
                bs.usuario_id
            FROM broker_sellers bs
            WHERE bs.id = :id
              AND bs.broker_id = :broker_id
            """
        ),
        {"id": seller_id, "broker_id": broker.id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado en tu equipo")
    return _serialize_team_member(row)


def _resolve_broker(db: Session, usuario_id: int):
    broker = db.execute(
        text("SELECT id, nombre FROM brokers WHERE usuario_id = :usuario_id"),
        {"usuario_id": usuario_id},
    ).fetchone()
    if not broker:
        raise HTTPException(status_code=404, detail="No encontramos un broker asociado a tu cuenta")
    return broker


def _serialize_team_member(row) -> dict:
    return {
        "id": row.id,
        "nombre": row.nombre,
        "email": row.email,
        "referral_code": row.referral_code,
        "estado": row.estado,
        "fecha_alta": row.fecha_alta.isoformat() if row.fecha_alta else None,
        "usuario_id": row.usuario_id,
        "link_referido": f"/?ref={row.referral_code}",
    }
