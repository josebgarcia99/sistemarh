"""Punto de entrada de la API.

Ejecutar en desarrollo:  uvicorn app.main:app --reload
"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, FastAPI

from app.composition.backend import Backend
from app.composition.context import AppContext
from app.core.clock import Clock, utc_now
from app.core.config.settings import Environment, Settings, get_settings
from app.core.exceptions.errors import register_exception_handlers
from app.core.logging.setup import configure_logging
from app.core.middleware.correlation import RequestContextMiddleware
from app.core.security.passwords import Argon2Hasher, PasswordHasher
from app.modules.audit.api.router import router as audit_router
from app.modules.authentication.api.router import router as auth_router
from app.modules.authentication.domain.models import AuthPolicy
from app.modules.system.api.router import router as system_router
from app.modules.system.application.health import HealthCheck
from app.modules.system.infrastructure.checks import build_default_checks
from app.modules.users.api.router import router as users_router


def build_sql_backend(settings: Settings) -> Backend | None:
    """Backend sobre SQL Server, o ``None`` si aún no hay base configurada."""
    if settings.database_url is None:
        return None
    from app.composition.sql_backend import SqlBackend
    from app.infrastructure.database.engine import get_session_factory

    try:
        factory = get_session_factory(settings.database_url.get_secret_value())
    except ImportError as error:
        raise RuntimeError(
            "No se pudo cargar el controlador de SQL Server. Instala "
            "Microsoft ODBC Driver 18 for SQL Server en este equipo."
        ) from error
    return SqlBackend(factory)


def create_app(
    settings: Settings | None = None,
    health_checks: Mapping[str, HealthCheck] | None = None,
    *,
    backend: Backend | None = None,
    hasher: PasswordHasher | None = None,
    clock: Clock = utc_now,
    auth_policy: AuthPolicy | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # La documentación interactiva no se publica en producción.
    docs_enabled = settings.environment is not Environment.PRODUCTION
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
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
    )

    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    api = APIRouter(prefix=settings.api_prefix)
    api.include_router(system_router)
    api.include_router(auth_router)
    api.include_router(users_router)
    api.include_router(audit_router)
    app.include_router(api)
    return app


app = create_app()
