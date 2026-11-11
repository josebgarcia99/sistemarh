"""Evaluación de CV por lotes.

El mensaje lleva solo el identificador del lote. El estado y los resultados
viven en SQL Server: si el worker se reinicia a la mitad, lo ya evaluado está
guardado y el lote se reanuda desde el siguiente CV pendiente.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from celery import shared_task
from celery.signals import worker_ready

from app.composition.bootstrap import build_context
from app.composition.context import AppContext
from app.composition.cv_jobs import TASK_NAME, resume_interrupted, run_batch
from app.core.config.settings import get_settings


@lru_cache(maxsize=1)
def _context() -> AppContext:
    return build_context(get_settings(), job_mode="celery")


@shared_task(name=TASK_NAME)
def process_batch(batch_id: str) -> None:
    run_batch(_context(), uuid.UUID(batch_id))


@worker_ready.connect
def _resume_on_start(**_: object) -> None:
    """Al arrancar, vuelve a encolar los lotes que quedaron en curso."""
    context = _context()
    if context.backend is not None and context.settings.redis_url is not None:
        resume_interrupted(context)
