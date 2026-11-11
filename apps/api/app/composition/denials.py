"""Auditoría de accesos denegados.

Cualquier intento rechazado por falta de permiso queda registrado, también
cuando la respuesta es "no encontrado" para no revelar que el recurso existe.
Se registra aquí, después de que la transacción de la operación ya se revirtió,
en una transacción propia: así el rechazo no deja cambios y el evento no se
pierde.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.composition.context import AppContext, client_ip
from app.core.exceptions.errors import (
    AccessHiddenError,
    AppError,
    PermissionDeniedError,
    problem_response,
)
from app.modules.audit.domain.models import AuditAction, AuditResult

logger = logging.getLogger(__name__)


def _record_denial(request: Request, exc: AppError) -> None:
    context: AppContext = request.app.state.context
    if context.backend is None:
        return
    with context.backend.transaction() as repos:
        context.audit(repos).record(
            AuditAction.ACCESO_DENEGADO,
            result=AuditResult.DENEGADO,
            actor_user_id=getattr(request.state, "user_id", None),
            resource_type="ruta",
            resource_id=request.url.path[:64],
            ip=client_ip(request),
            details={
                "metodo": request.method,
                "ruta": request.url.path[:300],
                "motivo": exc.code,
            },
        )


def register_denial_audit(app: FastAPI) -> None:
    async def _denied(request: Request, exc: AppError) -> JSONResponse:
        try:
            await run_in_threadpool(_record_denial, request, exc)
        except Exception:
            # El rechazo se responde igual; el fallo de auditoría queda en el log.
            logger.exception("No se pudo auditar un acceso denegado")
        return problem_response(exc)

    app.add_exception_handler(PermissionDeniedError, _denied)
    app.add_exception_handler(AccessHiddenError, _denied)
