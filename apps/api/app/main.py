"""Punto de entrada de la API.

Ejecutar en desarrollo:  uvicorn app.main:app --reload
"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, FastAPI

from app.core.config.settings import Environment, Settings, get_settings
from app.core.exceptions.errors import register_exception_handlers
from app.core.logging.setup import configure_logging
from app.core.middleware.correlation import RequestContextMiddleware
from app.modules.system.api.router import router as system_router
from app.modules.system.application.health import HealthCheck
from app.modules.system.infrastructure.checks import build_default_checks


def create_app(
    settings: Settings | None = None,
    health_checks: Mapping[str, HealthCheck] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # La documentación interactiva no se publica en producción.
    docs_enabled = settings.environment is not Environment.PRODUCTION
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json" if docs_enabled else None,
        docs_url=f"{settings.api_prefix}/docs" if docs_enabled else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.health_checks = (
        health_checks if health_checks is not None else build_default_checks(settings)
    )

    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    api = APIRouter(prefix=settings.api_prefix)
    api.include_router(system_router)
    app.include_router(api)
    return app


app = create_app()
