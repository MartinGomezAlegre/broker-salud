from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


def obtener_rol_panel_empresas(db: Session, usuario_id: int) -> str:
    usuario = db.execute(
        text("SELECT rol FROM usuarios WHERE id = :id"),
        {"id": usuario_id},
    ).fetchone()
    if not usuario or usuario.rol not in ("admin", "gestor_interno"):
        raise HTTPException(status_code=403, detail="No tenes permisos para acceder a empresas.")
    return usuario.rol


def aplicar_scope_empresas(
    db: Session,
    condiciones: list[str],
    params: dict,
    usuario_id: int,
    *,
    alias: str = "e",
) -> str:
    rol = obtener_rol_panel_empresas(db, usuario_id)
    if rol == "gestor_interno":
        condiciones.append(f"COALESCE({alias}.visible_para_gestores, false) = true")
    return rol


def asegurar_acceso_empresa(db: Session, usuario_id: int, empresa_id: int) -> str:
    rol = obtener_rol_panel_empresas(db, usuario_id)
    if rol == "admin":
        return rol

    permitido = db.execute(
        text(
            """
            SELECT 1
            FROM empresas
            WHERE id = :empresa_id
              AND COALESCE(visible_para_gestores, false) = true
            """
        ),
        {"empresa_id": empresa_id},
    ).fetchone()
    if not permitido:
        raise HTTPException(status_code=403, detail="No tenes acceso a esta empresa.")
    return rol
