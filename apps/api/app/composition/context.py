"""Dependencias compartidas por las rutas: datos, reloj, hasher y política."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.composition.backend import Backend, Repositories
from app.core.clock import Clock
from app.core.config.settings import Settings
from app.core.exceptions.errors import ServiceUnavailableError
from app.core.security.passwords import PasswordHasher
from app.modules.audit.application.service import AuditLog
from app.modules.authentication.application.service import AuthService
from app.modules.authentication.domain.models import AuthPolicy
from app.modules.users.application.service import UserService


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    backend: Backend | None
    hasher: PasswordHasher
    clock: Clock
    auth_policy: AuthPolicy

    def require_backend(self) -> Backend:
        if self.backend is None:
            raise ServiceUnavailableError(
                "La base de datos no está configurada. Define RECLU_DATABASE_URL."
            )
        return self.backend

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


def get_context(request: Request) -> AppContext:
    return request.app.state.context


def client_ip(request: Request) -> str | None:
    # El proxy inverso es quien debe fijar la IP real; aquí se toma la del socket.
    return request.client.host if request.client else None
