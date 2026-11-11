"""Evento de auditoría. Solo se inserta; nunca se modifica ni se borra."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class AuditResult(StrEnum):
    PERMITIDO = "PERMITIDO"
    DENEGADO = "DENEGADO"
    FALLIDO = "FALLIDO"


class AuditAction(StrEnum):
    SESION_INICIO = "sesion.inicio"
    SESION_INICIO_FALLIDO = "sesion.inicio_fallido"
    SESION_CIERRE = "sesion.cierre"
    ACCESO_DENEGADO = "acceso.denegado"
    USUARIO_CREADO = "usuario.creado"
    USUARIO_ACTUALIZADO = "usuario.actualizado"
    USUARIO_CONTRASENA_RESTABLECIDA = "usuario.contrasena_restablecida"
    USUARIO_DESACTIVADO = "usuario.desactivado"
    USUARIO_ACTIVADO = "usuario.activado"


@dataclass(frozen=True)
class AuditEvent:
    id: uuid.UUID
    occurred_at: datetime
    action: str
    result: AuditResult
    actor_user_id: uuid.UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    ip: str | None = None
    correlation_id: str | None = None
    # Nunca contraseñas, claves ni contenido de documentos.
    details: dict[str, Any] = field(default_factory=dict)


class AuditRepository(Protocol):
    def add(self, event: AuditEvent) -> None: ...

    def list(
        self, *, action: str | None, offset: int, limit: int
    ) -> tuple[list[AuditEvent], int]: ...
