from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.database import SessionLocal
from app.services.admin.jobs import enviar_recordatorios, procesar_vencimientos
from app.services.email.notifications import (
    enviar_email_bienvenida,
    enviar_email_invitacion_cuenta,
    enviar_email_lead_empresarial,
    enviar_email_plan_vencido,
    enviar_email_recuperacion,
    enviar_email_suscripcion_activa,
    enviar_email_ticket_recibido,
    enviar_email_ticket_respondido,
    enviar_email_vencimiento_proximo,
)
from app.services.pagos.mercadopago import procesar_webhook_mercadopago

TASK_PROCESAR_VENCIMIENTOS = "admin.procesar_vencimientos"
TASK_ENVIAR_RECORDATORIOS = "admin.enviar_recordatorios"
TASK_PROCESAR_MERCADOPAGO_WEBHOOK = "payments.process_mercadopago_webhook"


def _run_with_session(service: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    with SessionLocal() as db:
        return service(db, *args, **kwargs)


def _procesar_vencimientos_job() -> Any:
    return _run_with_session(procesar_vencimientos)


def _enviar_recordatorios_job() -> Any:
    return _run_with_session(enviar_recordatorios)


def _procesar_webhook_mercadopago_job(webhook_id: int) -> Any:
    return _run_with_session(procesar_webhook_mercadopago, webhook_id)


EMAIL_TASKS: dict[str, Callable[..., Any]] = {
    "email.bienvenida": enviar_email_bienvenida,
    "email.invitacion_cuenta": enviar_email_invitacion_cuenta,
    "email.recuperacion": enviar_email_recuperacion,
    "email.suscripcion_activa": enviar_email_suscripcion_activa,
    "email.vencimiento_proximo": enviar_email_vencimiento_proximo,
    "email.plan_vencido": enviar_email_plan_vencido,
    "email.ticket_recibido": enviar_email_ticket_recibido,
    "email.ticket_respondido": enviar_email_ticket_respondido,
    "email.lead_empresarial": enviar_email_lead_empresarial,
}

JOB_TASKS: dict[str, Callable[..., Any]] = {
    TASK_PROCESAR_VENCIMIENTOS: _procesar_vencimientos_job,
    TASK_ENVIAR_RECORDATORIOS: _enviar_recordatorios_job,
    TASK_PROCESAR_MERCADOPAGO_WEBHOOK: _procesar_webhook_mercadopago_job,
}

TASK_REGISTRY: dict[str, Callable[..., Any]] = {
    **EMAIL_TASKS,
    **JOB_TASKS,
}

CALLABLE_TO_TASK_NAME = {func: name for name, func in EMAIL_TASKS.items()}


def resolve_email_task_name(email_sender: Callable[..., Any]) -> str | None:
    return CALLABLE_TO_TASK_NAME.get(email_sender)


def run_registered_task(task_name: str, args: list[Any] | tuple[Any, ...], kwargs: dict[str, Any] | None = None) -> Any:
    task = TASK_REGISTRY.get(task_name)
    if task is None:
        raise ValueError(f"Task no registrada: {task_name}")

    return task(*args, **(kwargs or {}))
