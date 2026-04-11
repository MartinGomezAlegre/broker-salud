from collections.abc import Callable

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db


def require_roles(*roles: str) -> Callable:
    def dependency(
        db: Session = Depends(get_db),
        usuario_id: int = Depends(get_current_user),
    ):
        usuario = db.execute(
            text("SELECT rol FROM usuarios WHERE id = :id"),
            {"id": usuario_id},
        ).fetchone()
        if not usuario or usuario.rol not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Acceso denegado: se requiere alguno de estos roles: {', '.join(roles)}",
            )
        return usuario_id

    return dependency


def require_admin(
    usuario_id: int = Depends(require_roles("admin")),
):
    return usuario_id
