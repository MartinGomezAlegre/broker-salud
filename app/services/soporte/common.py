import logging

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.routers.admin_common import require_admin

logger = logging.getLogger(__name__)

ESTADOS_TICKET = {"abierto", "respondido", "cerrado"}


def require_admin_dep(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(get_current_user),
):
    return require_admin(db=db, usuario_id=usuario_id)


def obtener_columnas_tickets(db: Session) -> set[str]:
    columnas = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tickets_soporte'
            """
        )
    ).scalars().all()
    return set(columnas)


def columna_mensaje_ticket(columnas: set[str]) -> str | None:
    if "mensaje" in columnas:
        return "mensaje"
    if "descripcion" in columnas:
        return "descripcion"
    return None


def select_mensaje_ticket(columnas: set[str], alias: str = "t") -> str:
    columna = columna_mensaje_ticket(columnas)
    if columna:
        return f"{alias}.{columna} AS mensaje"
    return "NULL::text AS mensaje"


def select_texto_opcional(columnas: set[str], columna: str, alias: str = "t", as_name: str | None = None) -> str:
    nombre = as_name or columna
    if columna in columnas:
        return f"{alias}.{columna} AS {nombre}"
    return f"NULL::text AS {nombre}"


def select_timestamp_opcional(columnas: set[str], columna: str, alias: str = "t", as_name: str | None = None) -> str:
    nombre = as_name or columna
    if columna in columnas:
        return f"{alias}.{columna} AS {nombre}"
    return f"NULL::timestamp AS {nombre}"
