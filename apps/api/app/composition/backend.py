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

from app.composition.study_queue import SqlStudyQueue
from app.modules.ai_settings.domain.models import AiRepository
from app.modules.assessments.domain.models import AssessmentRepository
from app.modules.audit.domain.models import AuditRepository
from app.modules.authentication.domain.models import SessionRepository
from app.modules.cv_processing.domain.models import CvBatchRepository
from app.modules.evaluation_setup.domain.models import EvaluationSetupRepository
from app.modules.file_management.domain.models import FileRepository
from app.modules.phone_calls.domain.models import PhoneCallRepository
from app.modules.recruitment.domain.models import RecruitmentRepository
from app.modules.reporting.domain.models import ReportingSource
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
    cv_batches: CvBatchRepository
    recruitment: RecruitmentRepository
    phone_calls: PhoneCallRepository
    assessments: AssessmentRepository
    reporting: ReportingSource
    study_queue: SqlStudyQueue


class Backend(Protocol):
    def transaction(self) -> AbstractContextManager[Repositories]: ...
