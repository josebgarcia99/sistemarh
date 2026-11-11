"""Aplicación Celery del sistema.

Redis se usa solo como intermediario de tareas. El estado de cada trabajo vive
en SQL Server, por lo que no se configura backend de resultados: si Redis se
pierde, la cola se reconstruye desde la base de datos.

Ejecutar en desarrollo:  celery -A worker.celery_app worker --loglevel=INFO
"""

from __future__ import annotations

from celery import Celery

from app.core.config.settings import Settings, get_settings
from app.core.logging.setup import configure_logging


def create_celery_app(settings: Settings | None = None) -> Celery:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    broker_url = settings.redis_url.get_secret_value() if settings.redis_url else None
    celery_app = Celery("reclutamiento", broker=broker_url, include=["worker.jobs.system"])
    celery_app.conf.update(
        # Los mensajes llevan solo identificadores, nunca contenido ni secretos.
        task_serializer="json",
        accept_content=["json"],
        result_backend=None,
        task_ignore_result=True,
        # Una tarea se confirma al terminar: si el worker muere, se reentrega.
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        timezone="UTC",
        enable_utc=True,
        # Celery no debe secuestrar el registro: se conserva el filtro de secretos.
        worker_hijack_root_logger=False,
        broker_connection_retry_on_startup=True,
    )
    return celery_app


celery_app = create_celery_app()
