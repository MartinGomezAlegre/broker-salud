from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.limiter import get_client_ip

logger = logging.getLogger(__name__)


def log_audit_event(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    request: Request | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        ip_address = get_client_ip(request) if request is not None else None
        user_agent = request.headers.get("user-agent") if request is not None else None

        db.execute(
            text(
                """
                INSERT INTO audit_log (
                    actor_user_id,
                    action,
                    entity_type,
                    entity_id,
                    ip_address,
                    user_agent,
                    metadata
                )
                VALUES (
                    :actor_user_id,
                    :action,
                    :entity_type,
                    :entity_id,
                    :ip_address,
                    :user_agent,
                    CAST(:metadata AS JSONB)
                )
                """
            ),
            {
                "actor_user_id": actor_user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id is not None else None,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "metadata": json.dumps(metadata or {}),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("No se pudo registrar audit_log %s/%s: %s", entity_type, action, exc, exc_info=True)
