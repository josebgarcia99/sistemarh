"""Dependencias compartidas por las rutas: datos, reloj, hasher y política."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request

from app.composition.backend import Backend, Repositories
from app.composition.file_access import VacancyFileAccessPolicy
from app.core.clock import Clock
from app.core.config.settings import Settings
from app.core.exceptions.errors import ServiceUnavailableError
from app.core.security.passwords import PasswordHasher
from app.infrastructure.antivirus.scanner import DisabledScanner, MalwareScanner
from app.infrastructure.storage.local import LocalFileStorage
from app.modules.audit.application.service import AuditLog
from app.modules.authentication.application.service import AuthService
from app.modules.authentication.domain.models import AuthPolicy
from app.modules.file_management.application.reconciliation import StorageReconciler
from app.modules.file_management.application.service import FileService, UploadPipeline
from app.modules.users.application.service import UserService
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
        return UploadPipeline(self.require_storage(), self.scanner, self.settings.max_upload_bytes)

    def file_service(self, repos: Repositories) -> FileService:
        return FileService(
            repos.files,
            VacancyFileAccessPolicy(repos.vacancies),
            self.audit(repos),
            self.clock,
            self.require_storage(),
            max_bytes=self.settings.max_upload_bytes,
            min_free_bytes=self.settings.storage_min_free_bytes,
            allow_sensitive=self.settings.allow_unencrypted_sensitive_files,
        )

    def reconciler(self, repos: Repositories) -> StorageReconciler:
        return StorageReconciler(repos.files, self.require_storage(), self.audit(repos), self.clock)

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
