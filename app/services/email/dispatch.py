from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import BackgroundTasks

from app.jobs.queue import enqueue_job
from app.jobs.tasks import resolve_email_task_name

logger = logging.getLogger(__name__)


def _run_email_task(
    email_sender: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    try:
        email_sender(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - side effect externo
        logger.error(
            "Error ejecutando tarea de email %s: %s",
            getattr(email_sender, "__name__", repr(email_sender)),
            exc,
            exc_info=True,
        )


def dispatch_email(
    background_tasks: BackgroundTasks | None,
    email_sender: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    task_name = resolve_email_task_name(email_sender)
    if task_name and enqueue_job(task_name, *args, **kwargs):
        logger.info("Email %s encolado en Redis.", task_name)
        return

    if background_tasks is None:
        _run_email_task(email_sender, *args, **kwargs)
        return

    background_tasks.add_task(_run_email_task, email_sender, *args, **kwargs)
