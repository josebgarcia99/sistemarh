"""Ejecución en segundo plano de los lotes de CV.

El estado vive en SQL Server; la cola solo transporta el identificador del
lote. Cada CV se confirma en su propia transacción, así que un proceso que
muere a la mitad no pierde lo ya evaluado: basta reanudar el lote.
"""

from __future__ import annotations

import logging
import threading
import uuid
from functools import lru_cache
from typing import TYPE_CHECKING

from app.modules.cv_processing.application.service import StepOutcome

if TYPE_CHECKING:
    from app.composition.context import AppContext

logger = logging.getLogger(__name__)

TASK_NAME = "cv.process_batch"
# Fallos seguidos del proveedor que detienen el lote en lugar de agotar todos los CV.
_MAX_CONSECUTIVE_PROVIDER_FAILURES = 3


def run_batch(context: AppContext, batch_id: uuid.UUID) -> None:
    backend = context.require_backend()
    token = uuid.uuid4().hex

    def stop(message: str) -> None:
        with backend.transaction() as repos:
            context.cv_batches(repos).stop(batch_id, message)

    with backend.transaction() as repos:
        if not context.cv_batches(repos).claim(batch_id, token):
            return
    provider_failures = 0
    while True:
        try:
            with backend.transaction() as repos:
                outcome = context.cv_batches(repos).process_next(batch_id, token)
        except Exception:
            logger.exception("Error inesperado al procesar un lote de CV")
            stop("Ocurrió un error inesperado. Lo ya evaluado está guardado; usa «Reintentar».")
            return
        if outcome is StepOutcome.STOPPED:
            return
        if outcome is StepOutcome.NO_MORE:
            break
        provider_failures = provider_failures + 1 if outcome is StepOutcome.PROVIDER_FAILED else 0
        if provider_failures >= _MAX_CONSECUTIVE_PROVIDER_FAILURES:
            stop(
                "El proveedor de IA no está respondiendo. Lo ya evaluado está guardado; "
                "usa «Reintentar» más tarde."
            )
            return
    try:
        with backend.transaction() as repos:
            context.cv_batches(repos).finalize(batch_id, token)
            vacancy_id = repos.cv_batches.get_batch(batch_id).vacancy_id
    except Exception:
        logger.exception("Error inesperado al cerrar un lote de CV")
        stop("No se pudo cerrar el lote. Lo ya evaluado está guardado; usa «Reintentar».")
        return
    try:
        # Cada CV evaluado entra al proceso como postulación, en revisión de RH.
        with backend.transaction() as repos:
            context.recruitment(repos).sync_evaluated(vacancy_id)
    except Exception:
        # No se pierde nada: se vuelve a intentar al abrir los candidatos de la vacante.
        logger.exception("No se pudieron registrar las postulaciones de un lote de CV")


@lru_cache(maxsize=1)
def _producer(broker_url: str):  # noqa: ANN202
    from celery import Celery

    return Celery("reclutamiento-api", broker=broker_url)


def dispatch(context: AppContext, batch_id: uuid.UUID) -> None:
    """Entrega el lote para procesarlo. ``job_mode``:

    - ``celery``: lo toma el worker (producción y contenedores).
    - ``thread``: un hilo de la propia API (equipo de desarrollo sin Redis).
    - ``inline``: en el momento (pruebas y modo demostración).
    """
    mode = context.job_mode
    if mode == "inline":
        run_batch(context, batch_id)
    elif mode == "celery":
        url = context.settings.redis_url
        if url is None:
            raise RuntimeError("Falta RECLU_REDIS_URL para encolar trabajos.")
        _producer(url.get_secret_value()).send_task(TASK_NAME, args=[str(batch_id)])
    else:
        threading.Thread(
            target=run_batch, args=(context, batch_id), name=f"lote-cv-{batch_id}", daemon=True
        ).start()


def resume_interrupted(context: AppContext) -> int:
    """Vuelve a entregar los lotes que quedaron en curso (por ejemplo, tras reiniciar)."""
    with context.require_backend().transaction() as repos:
        batch_ids = repos.cv_batches.active_batch_ids()
    for batch_id in batch_ids:
        dispatch(context, batch_id)
    return len(batch_ids)
