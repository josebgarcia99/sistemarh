"""Acceso a datos por transacción.

``Backend.transaction()`` abre una unidad de trabajo: confirma al salir sin
errores y revierte si hubo una excepción. Dentro de ella, los módulos reciben
sus repositorios. La única implementación es ``SqlBackend`` (SQLAlchemy sobre
SQL Server); las pruebas la ejecutan sobre un motor en memoria.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from app.modules.ai_settings.domain.models import AiRepository
from app.modules.audit.domain.models import AuditRepository
from app.modules.authentication.domain.models import SessionRepository
from app.modules.evaluation_setup.domain.models import EvaluationSetupRepository
from app.modules.file_management.domain.models import FileRepository
from app.modules.users.domain.repository import UserRepository
from app.modules.vacancies.domain.models import VacancyRepository
from app.modules.vacancy_transfers.domain.models import TransferRepository


@dataclass(frozen=True)
class Repositories:
    users: UserRepository
    sessions: SessionRepository
    audit: AuditRepository
    vacancies: VacancyRepository
    transfers: TransferRepository
    files: FileRepository
    ai: AiRepository
    evaluation_setup: EvaluationSetupRepository


class Backend(Protocol):
    def transaction(self) -> AbstractContextManager[Repositories]: ...
