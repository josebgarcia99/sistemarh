"""Punto de entrada de la API.

Ejecutar en desarrollo:  uvicorn app.main:app --reload
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from fastapi import APIRouter, FastAPI

from app.composition.ai import build_provider_clients
from app.composition.backend import Backend
from app.composition.bootstrap import (
    build_master_key,
    build_ocr,
    build_scanner,
    build_sql_backend,
    build_storage,
    default_job_mode,
)
from app.composition.context import AppContext
from app.composition.denials import register_denial_audit
from app.core.clock import Clock, utc_now
from app.core.config.settings import Environment, Settings, get_settings
from app.core.exceptions.errors import register_exception_handlers
from app.core.logging.setup import configure_logging
from app.core.middleware.correlation import RequestContextMiddleware
from app.core.security.master_key import MasterKey
from app.core.security.passwords import Argon2Hasher, PasswordHasher
from app.infrastructure.antivirus.scanner import MalwareScanner
from app.infrastructure.storage.local import LocalFileStorage
from app.modules.ai_settings.api.router import router as ai_router
from app.modules.ai_settings.domain.models import ProviderClient, ProviderCode
from app.modules.audit.api.router import router as audit_router
from app.modules.authentication.api.router import router as auth_router
from app.modules.authentication.domain.models import AuthPolicy
from app.modules.cv_processing.api.router import router as cv_processing_router
from app.modules.evaluation_setup.api.router import router as evaluation_setup_router
from app.modules.file_management.api.router import router as files_router
from app.modules.phone_calls.api.router import router as phone_calls_router
from app.modules.recruitment.api.router import router as recruitment_router
from app.modules.system.api.router import router as system_router
from app.modules.system.application.health import HealthCheck
from app.modules.system.infrastructure.checks import build_default_checks
from app.modules.users.api.router import router as users_router
from app.modules.vacancies.api.router import router as vacancies_router
from app.modules.vacancy_transfers.api.router import router as transfers_router


def create_app(
    settings: Settings | None = None,
    health_checks: Mapping[str, HealthCheck] | None = None,
    *,
    backend: Backend | None = None,
    hasher: PasswordHasher | None = None,
    clock: Clock = utc_now,
    auth_policy: AuthPolicy | None = None,
    storage: LocalFileStorage | None = None,
    scanner: MalwareScanner | None = None,
    master_key: MasterKey | None = None,
    ai_clients: dict[ProviderCode, ProviderClient] | None = None,
    ai_sleep: Callable[[float], None] = time.sleep,
    job_mode: str | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # La documentación interactiva no se publica en producción.
    docs_enabled = settings.environment is not Environment.PRODUCTION
    app = FastAPI(
        title=settings.app_name,
        version="0.6.0",
        openapi_url=f"{settings.api_prefix}/openapi.json" if docs_enabled else None,
        docs_url=f"{settings.api_prefix}/docs" if docs_enabled else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.health_checks = (
        health_checks if health_checks is not None else build_default_checks(settings)
    )
    app.state.context = AppContext(
        settings=settings,
        backend=backend if backend is not None else build_sql_backend(settings),
        hasher=hasher or Argon2Hasher(),
        clock=clock,
        auth_policy=auth_policy or AuthPolicy(),
        storage=storage if storage is not None else build_storage(settings),
        scanner=scanner or build_scanner(settings),
        master_key=master_key if master_key is not None else build_master_key(settings),
        ai_clients=ai_clients if ai_clients is not None else build_provider_clients(settings),
        ai_sleep=ai_sleep,
        job_mode=job_mode or default_job_mode(settings),
        ocr=build_ocr(settings),
    )

    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    register_denial_audit(app)

    api = APIRouter(prefix=settings.api_prefix)
    api.include_router(system_router)
    api.include_router(auth_router)
    api.include_router(users_router)
    api.include_router(vacancies_router)
    api.include_router(transfers_router)
    api.include_router(files_router)
    api.include_router(ai_router)
    api.include_router(evaluation_setup_router)
    api.include_router(cv_processing_router)
    api.include_router(recruitment_router)
    api.include_router(phone_calls_router)
    api.include_router(audit_router)
    app.include_router(api)
    return app


app = create_app()
