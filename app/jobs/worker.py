from __future__ import annotations

import json
import logging
import time

from app.jobs.queue import ack_job, claim_job, enqueue_job, is_queue_available, requeue_processing_jobs
from app.jobs.tasks import run_registered_task
from app.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_worker() -> None:
    settings = get_settings()

    if not is_queue_available():
        raise RuntimeError("REDIS_URL no esta configurada o Redis no esta disponible para el worker.")

    recovered = requeue_processing_jobs()
    if recovered:
        logger.info("Se reencolaron %s jobs pendientes de una ejecucion anterior.", recovered)

    logger.info("Worker escuchando cola %s", settings.job_queue_name)

    while True:
        payload = claim_job(timeout=5)
        if payload is None:
            continue

        try:
            job = json.loads(payload)
            task_name = job["task"]
            args = job.get("args", [])
            kwargs = job.get("kwargs", {})
            attempts = int(job.get("attempts", 0))

            run_registered_task(task_name, args, kwargs)
            ack_job(payload)
            logger.info("Job %s completado.", task_name)
        except KeyboardInterrupt:  # pragma: no cover - control manual
            raise
        except Exception as exc:  # pragma: no cover - depende de integraciones externas
            attempts = int(job.get("attempts", 0)) if "job" in locals() else 0
            task_name = job.get("task", "unknown") if "job" in locals() else "unknown"
            logger.error("Error ejecutando job %s: %s", task_name, exc, exc_info=True)
            ack_job(payload)

            if attempts < settings.job_retry_limit:
                requeued = enqueue_job(
                    task_name,
                    *job.get("args", []),
                    attempts=attempts + 1,
                    **job.get("kwargs", {}),
                )
                if requeued:
                    logger.info("Job %s reencolado para reintento %s.", task_name, attempts + 1)
                else:
                    logger.error("No se pudo reencolar job %s luego del error.", task_name)
            else:
                logger.error(
                    "Job %s agotado tras %s intentos. Se descarta hasta reenvio manual.",
                    task_name,
                    attempts + 1,
                )

        time.sleep(0.05)


if __name__ == "__main__":  # pragma: no cover - entry point manual
    run_worker()
