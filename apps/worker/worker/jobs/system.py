"""Tareas de sistema. Sirven para comprobar que la cola y el worker funcionan."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="system.ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
