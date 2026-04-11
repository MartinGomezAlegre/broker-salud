import logging

from fastapi import Depends
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
