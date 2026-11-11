"""Registro de auditoría."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.clock import Clock
from app.core.ids import new_sequential_uuid
from app.core.logging.setup import correlation_id_var
from app.modules.audit.domain.models import AuditEvent, AuditRepository, AuditResult

_FORBIDDEN_DETAIL_KEYS = {"password", "contrasena", "contraseña", "token", "api_key", "secret"}


class AuditLog:
    def __init__(self, repository: AuditRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def record(
        self,
        action: str,
        *,
        result: AuditResult = AuditResult.PERMITIDO,
        actor_user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | str | None = None,
        ip: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        details = details or {}
        forbidden = _FORBIDDEN_DETAIL_KEYS & {key.lower() for key in details}
        if forbidden:
            # Error de programación: se detiene antes de escribir un secreto.
            raise ValueError(f"La auditoría no admite estos campos: {sorted(forbidden)}")
        event = AuditEvent(
            id=new_sequential_uuid(),
            occurred_at=self._clock(),
            action=str(action),
            result=result,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=None if resource_id is None else str(resource_id),
            ip=ip,
            correlation_id=correlation_id_var.get(),
            details=details,
        )
        self._repository.add(event)
        return event

    def list(self, *, action: str | None, offset: int, limit: int) -> tuple[list[AuditEvent], int]:
        return self._repository.list(action=action, offset=offset, limit=limit)
