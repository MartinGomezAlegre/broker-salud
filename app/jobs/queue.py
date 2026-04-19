from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from app.settings import get_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - depende del entorno
    from redis import Redis
except ImportError:  # pragma: no cover - fallback para dev sin dependencia
    Redis = None  # type: ignore[assignment]


settings = get_settings()


def _processing_queue_name() -> str:
    return f"{settings.job_queue_name}:processing"


@lru_cache(maxsize=1)
def _get_redis_client() -> Redis | None:
    if not settings.redis_url:
        return None

    if Redis is None:
        logger.warning("REDIS_URL configurada pero redis no esta instalado.")
        return None

    return Redis.from_url(settings.redis_url, decode_responses=True)


def is_queue_available() -> bool:
    return _get_redis_client() is not None


def _build_payload(
    task_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any] | None,
    attempts: int,
) -> str:
    return json.dumps({
        "task": task_name,
        "args": list(args),
        "kwargs": kwargs or {},
        "attempts": attempts,
    })


def enqueue_job(
    task_name: str,
    *args: Any,
    attempts: int = 0,
    **kwargs: Any,
) -> bool:
    client = _get_redis_client()
    if client is None:
        return False

    try:
        payload = _build_payload(task_name, args, kwargs, attempts)
        client.rpush(settings.job_queue_name, payload)
        return True
    except TypeError as exc:
        logger.error("Payload no serializable para job %s: %s", task_name, exc)
    except Exception as exc:  # pragma: no cover - depende de Redis externo
        logger.error("No se pudo encolar job %s: %s", task_name, exc, exc_info=True)

    return False


def requeue_processing_jobs() -> int:
    client = _get_redis_client()
    if client is None:
        return 0

    moved = 0
    processing_queue = _processing_queue_name()

    while True:
        payload = client.rpoplpush(processing_queue, settings.job_queue_name)
        if payload is None:
            break
        moved += 1

    return moved


def claim_job(timeout: int = 5) -> str | None:
    client = _get_redis_client()
    if client is None:
        return None

    return client.brpoplpush(settings.job_queue_name, _processing_queue_name(), timeout=timeout)


def ack_job(payload: str) -> None:
    client = _get_redis_client()
    if client is None:
        return

    client.lrem(_processing_queue_name(), 1, payload)
