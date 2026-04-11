from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db


def require_admin(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    usuario = db.execute(
        text("SELECT rol FROM usuarios WHERE id = :id"),
        {"id": usuario_id},
    ).fetchone()
    if not usuario or usuario.rol != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: se requiere rol admin")
    return usuario_id
