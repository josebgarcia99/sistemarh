"""Dependencias compartidas por las rutas: datos, reloj, hasher y política."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from fastapi import Request

from app.composition.ai import env_api_keys
from app.composition.assessments import (
    AssessmentApplications,
    AssessmentAssistant,
    AssessmentDocuments,
    VacancyAssessmentAccess,
)
from app.composition.backend import Backend, Repositories
from app.composition.cv_processing import (
    AiEvaluator,
    AiExtractor,
    ApprovedRubrics,
    StoredCvFiles,
)
from app.composition.evaluation_ai import AiAssistant, StoredProfileSources
from app.composition.file_access import VacancyFileAccessPolicy
from app.composition.recruitment import (
    BatchEvaluatedCvs,
    CallApplications,
    CallAssistant,
    VacancyProfiles,
)
from app.composition.reporting import StoredReports, can_read_study
from app.core.clock import Clock
from app.core.config.settings import Environment, Settings
from app.core.exceptions.errors import ServiceUnavailableError
from app.core.security.master_key import MasterKey
from app.core.security.passwords import PasswordHasher
from app.infrastructure.antivirus.scanner import DisabledScanner, MalwareScanner
from app.infrastructure.documents.text import Ocr
from app.infrastructure.storage.local import LocalFileStorage
from app.modules.ai_settings.application.service import AiSettingsService
from app.modules.ai_settings.domain.models import ProviderClient, ProviderCode
from app.modules.assessments.application.service import AssessmentService
from app.modules.audit.application.service import AuditLog
from app.modules.authentication.application.service import AuthService
from app.modules.authentication.domain.models import AuthPolicy
from app.modules.cv_processing.application.service import CvBatchService
from app.modules.evaluation_setup.application.service import EvaluationSetupService
from app.modules.file_management.application.reconciliation import StorageReconciler
from app.modules.file_management.application.service import FileService, UploadPipeline
from app.modules.phone_calls.application.service import PhoneCallService
from app.modules.recruitment.application.service import RecruitmentService
from app.modules.reporting.application.service import ReportingService
from app.modules.users.application.service import UserService
from app.modules.vacancies.application.access import VacancyAccess
from app.modules.vacancies.application.service import VacancyService
from app.modules.vacancy_transfers.application.service import TransferService


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    backend: Backend | None
    hasher: PasswordHasher
    clock: Clock
    auth_policy: AuthPolicy
    storage: LocalFileStorage | None = None
    scanner: MalwareScanner = field(default_factory=DisabledScanner)
    master_key: MasterKey | None = None
    ai_clients: dict[ProviderCode, ProviderClient] = field(default_factory=dict)
    # Espera entre reintentos de una llamada a un proveedor (las pruebas no esperan).
    ai_sleep: Callable[[float], None] = time.sleep
    # Cómo se ejecutan los trabajos en segundo plano: celery, thread o inline.
    job_mode: str = "thread"
    # Lector de documentos escaneados; ``None`` si está desactivado.
    ocr: Ocr | None = None

    def require_backend(self) -> Backend:
        if self.backend is None:
            raise ServiceUnavailableError(
                "La base de datos no está configurada. Define RECLU_DATABASE_URL."
            )
        return self.backend

    def require_storage(self) -> LocalFileStorage:
        if self.storage is None:
            raise ServiceUnavailableError(
                "El almacenamiento documental no está configurado. Define RECLU_STORAGE_ROOT."
            )
        return self.storage

    def upload_pipeline(self) -> UploadPipeline:
        return UploadPipeline(
            self.require_storage(),
            self.scanner,
            self.settings.max_upload_bytes,
            cipher=self.master_key,
        )

    def file_service(self, repos: Repositories) -> FileService:
        return FileService(
            repos.files,
            VacancyFileAccessPolicy(repos.vacancies),
            self.audit(repos),
            self.clock,
            self.require_storage(),
            max_bytes=self.settings.max_upload_bytes,
            min_free_bytes=self.settings.storage_min_free_bytes,
            encryption_available=self.master_key is not None,
            allow_unencrypted_sensitive=self.settings.allow_unencrypted_sensitive_files,
        )

    def reconciler(self, repos: Repositories) -> StorageReconciler:
        return StorageReconciler(
            repos.files,
            self.require_storage(),
            self.audit(repos),
            self.clock,
            # Los Excel de reportes tienen su propio registro.
            extra_known_keys=repos.reporting.export_keys,
        )

    def evaluation_setup(self, repos: Repositories) -> EvaluationSetupService:
        return EvaluationSetupService(
            repos.evaluation_setup,
            VacancyAccess(repos.vacancies),
            self.audit(repos),
            self.clock,
            assistant_port=AiAssistant(self.ai_settings(repos)),
            sources=StoredProfileSources(repos.files, self.storage, self.ocr),
        )

    def cv_batches(self, repos: Repositories) -> CvBatchService:
        return CvBatchService(
            repos.cv_batches,
            VacancyAccess(repos.vacancies),
            StoredCvFiles(repos.files, self.require_storage(), self.file_service(repos), self.ocr),
            ApprovedRubrics(repos.evaluation_setup),
            AiEvaluator(self.ai_settings(repos)),
            self.audit(repos),
            self.clock,
            extractor=AiExtractor(self.ai_settings(repos)),
        )

    def recruitment(self, repos: Repositories) -> RecruitmentService:
        return RecruitmentService(
            repos.recruitment,
            VacancyAccess(repos.vacancies),
            BatchEvaluatedCvs(repos.cv_batches, repos.files),
            self.audit(repos),
            self.clock,
        )

    def phone_calls(self, repos: Repositories) -> PhoneCallService:
        return PhoneCallService(
            repos.phone_calls,
            VacancyAccess(repos.vacancies),
            CallApplications(repos.recruitment, repos.cv_batches, repos.evaluation_setup),
            VacancyProfiles(repos.evaluation_setup),
            CallAssistant(self.ai_settings(repos)),
            self.audit(repos),
            self.clock,
        )

    def assessments(self, repos: Repositories) -> AssessmentService:
        return AssessmentService(
            repos.assessments,
            VacancyAssessmentAccess(repos.vacancies),
            AssessmentApplications(
                repos.recruitment, repos.cv_batches, repos.phone_calls, repos.evaluation_setup
            ),
            AssessmentDocuments(repos.files, self.storage, self.master_key, self.ocr),
            AssessmentAssistant(self.ai_settings(repos)),
            self.audit(repos),
            self.clock,
        )

    def reporting(self, repos: Repositories) -> ReportingService:
        return ReportingService(
            repos.reporting,
            StoredReports(self.storage) if self.storage is not None else None,
            self.audit(repos),
            self.clock,
            ZoneInfo(self.settings.display_timezone),
            can_read_study=lambda viewer, vacancy_id: can_read_study(
                repos.vacancies, viewer.user_id, viewer.is_admin, vacancy_id
            ),
        )

    def dispatch_cv_batch(self, batch_id: uuid.UUID) -> None:
        from app.composition.cv_jobs import dispatch

        dispatch(self, batch_id)

    def ai_settings(self, repos: Repositories) -> AiSettingsService:
        return AiSettingsService(
            repos.ai,
            self.audit(repos),
            self.clock,
            cipher=self.master_key,
            clients=self.ai_clients,
            env_keys=env_api_keys(self.settings),
            # Restricción 8: fuera de producción no se envían documentos a un
            # proveedor de IA salvo autorización expresa.
            documents_allowed=self.settings.ai_allow_real_documents
            or self.settings.environment is Environment.PRODUCTION,
            sleep=self.ai_sleep,
        )

    def audit(self, repos: Repositories) -> AuditLog:
        return AuditLog(repos.audit, self.clock)

    def auth_service(self, repos: Repositories) -> AuthService:
        return AuthService(
            repos.users,
            repos.sessions,
            self.audit(repos),
            self.hasher,
            self.clock,
            self.auth_policy,
        )

    def user_service(self, repos: Repositories) -> UserService:
        return UserService(repos.users, repos.sessions, self.audit(repos), self.hasher, self.clock)

    def transfer_service(self, repos: Repositories) -> TransferService:
        return TransferService(
            repos.vacancies,
            repos.transfers,
            repos.users,
            self.user_service(repos),
            self.audit(repos),
            self.clock,
        )

    def vacancy_service(self, repos: Repositories) -> VacancyService:
        return VacancyService(
            repos.vacancies,
            repos.users,
            self.audit(repos),
            self.clock,
            # El historial de responsables empieza al crear la vacante.
            on_created=self.transfer_service(repos).record_creation,
        )


def get_context(request: Request) -> AppContext:
    return request.app.state.context


def client_ip(request: Request) -> str | None:
    # El proxy inverso es quien debe fijar la IP real; aquí se toma la del socket.
    return request.client.host if request.client else None
