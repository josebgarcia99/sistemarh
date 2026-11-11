"""Acceso a datos por transacción.

``Backend.transaction()`` abre una unidad de trabajo: confirma al salir sin
errores y revierte si hubo una excepción. Dentro de ella, los módulos reciben
sus repositorios. Existen dos implementaciones: SQL Server (producción) y en
memoria (pruebas aisladas, mientras no haya una instancia de SQL Server).
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from app.modules.audit.domain.models import AuditRepository
from app.modules.authentication.domain.models import SessionRepository
from app.modules.users.domain.repository import UserRepository


@dataclass(frozen=True)
class Repositories:
    users: UserRepository
    sessions: SessionRepository
    audit: AuditRepository


class Backend(Protocol):
    def transaction(self) -> AbstractContextManager[Repositories]: ...
