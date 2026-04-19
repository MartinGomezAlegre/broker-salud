from fastapi import APIRouter, Depends

from app.database import SessionLocal
from app.internal_security import require_service_token
from app.jobs.queue import enqueue_job
from app.jobs.tasks import TASK_ENVIAR_RECORDATORIOS, TASK_PROCESAR_VENCIMIENTOS
from app.services.admin.jobs import enviar_recordatorios, procesar_vencimientos

router = APIRouter(prefix="/internal/jobs", tags=["internal-jobs"])


@router.post("/procesar-vencimientos")
def procesar_vencimientos_internal_route(
    _: bool = Depends(require_service_token),
):
    if enqueue_job(TASK_PROCESAR_VENCIMIENTOS):
        return {"queued": True, "job": TASK_PROCESAR_VENCIMIENTOS}

    with SessionLocal() as db:
        return {"queued": False, "result": procesar_vencimientos(db)}


@router.post("/enviar-recordatorios")
def enviar_recordatorios_internal_route(
    _: bool = Depends(require_service_token),
):
    if enqueue_job(TASK_ENVIAR_RECORDATORIOS):
        return {"queued": True, "job": TASK_ENVIAR_RECORDATORIOS}

    with SessionLocal() as db:
        return {"queued": False, "result": enviar_recordatorios(db)}
