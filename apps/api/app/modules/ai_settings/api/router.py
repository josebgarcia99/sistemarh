"""Configuración de inteligencia artificial. Solo administradores.

Ninguna respuesta incluye una API key: solo un identificador enmascarado con
sus últimos cuatro caracteres.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, SecretStr

from app.composition.backend import Repositories
from app.composition.context import AppContext, client_ip, get_context
from app.modules.ai_settings.application.service import ProviderView
from app.modules.ai_settings.domain.models import (
    PROVIDER_NAMES,
    Assignment,
    Model,
    Operation,
    ProviderCode,
)
from app.modules.authentication.api.dependencies import Principal, require_admin

router = APIRouter(prefix="/ai", tags=["inteligencia artificial"])


class ProviderOut(BaseModel):
    code: ProviderCode
    name: str
    enabled: bool
    key_configured: bool
    key_source: str | None
    key_mask: str | None
    key_updated_at: datetime | None
    key_updated_by_name: str | None
    last_test_at: datetime | None
    last_test_ok: bool | None
    last_test_error: str | None
    monthly_limit_usd: Decimal | None
    models_available: int


class AiOverviewOut(BaseModel):
    # Sin clave maestra no se pueden guardar API keys desde la pantalla.
    encryption_available: bool
    providers: list[ProviderOut]


class ApiKeyIn(BaseModel):
    # SecretStr: el valor no aparece en representaciones ni en errores de validación.
    api_key: SecretStr


class ProviderSettingsIn(BaseModel):
    enabled: bool
    monthly_limit_usd: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)


class TestResultOut(BaseModel):
    ok: bool
    error: str | None
    models_found: int
    provider: ProviderOut


class ModelOut(BaseModel):
    id: uuid.UUID
    provider_code: ProviderCode
    provider_name: str
    model_id: str
    display_name: str
    is_available: bool
    reports_capabilities: bool

    @classmethod
    def of(cls, model: Model) -> ModelOut:
        return cls(
            id=model.id,
            provider_code=model.provider_code,
            provider_name=PROVIDER_NAMES[model.provider_code],
            model_id=model.model_id,
            display_name=model.display_name,
            is_available=model.is_available,
            reports_capabilities=model.capabilities is not None,
        )


class AssignmentOut(BaseModel):
    operation: Operation
    model: ModelOut | None
    updated_at: datetime | None

    @classmethod
    def of(cls, assignment: Assignment, model: Model | None) -> AssignmentOut:
        return cls(
            operation=assignment.operation,
            model=ModelOut.of(model) if model else None,
            updated_at=assignment.updated_at,
        )


class AssignmentIn(BaseModel):
    model_id: uuid.UUID | None


def _provider_out(repos: Repositories, view: ProviderView) -> ProviderOut:
    author = repos.users.get(view.key_updated_by) if view.key_updated_by else None
    provider = view.provider
    return ProviderOut(
        code=provider.code,
        name=PROVIDER_NAMES[provider.code],
        enabled=provider.enabled,
        key_configured=view.key_source is not None,
        key_source=view.key_source.value if view.key_source else None,
        key_mask=view.key_mask,
        key_updated_at=view.key_updated_at,
        key_updated_by_name=author.full_name if author else None,
        last_test_at=provider.last_test_at,
        last_test_ok=provider.last_test_ok,
        last_test_error=provider.last_test_error,
        monthly_limit_usd=provider.monthly_limit_usd,
        models_available=view.models_available,
    )


@router.get(
    "/providers", response_model=AiOverviewOut, summary="Proveedores y estado de sus claves"
)
def list_providers(
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> AiOverviewOut:
    with context.require_backend().transaction() as repos:
        views = context.ai_settings(repos).overview(principal.user)
        providers = [_provider_out(repos, view) for view in views]
    return AiOverviewOut(encryption_available=context.master_key is not None, providers=providers)


@router.put(
    "/providers/{code}/key", response_model=ProviderOut, summary="Registra o sustituye la API key"
)
def set_key(
    code: ProviderCode,
    body: ApiKeyIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> ProviderOut:
    with context.require_backend().transaction() as repos:
        view = context.ai_settings(repos).set_key(
            principal.user, code, body.api_key.get_secret_value(), ip=client_ip(request)
        )
        return _provider_out(repos, view)


@router.delete("/providers/{code}/key", response_model=ProviderOut, summary="Revoca la API key")
def revoke_key(
    code: ProviderCode,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> ProviderOut:
    with context.require_backend().transaction() as repos:
        view = context.ai_settings(repos).revoke_key(principal.user, code, ip=client_ip(request))
        return _provider_out(repos, view)


@router.post(
    "/providers/{code}/test",
    response_model=TestResultOut,
    summary="Prueba la conexión y actualiza la lista de modelos (no envía documentos)",
)
def test_provider(
    code: ProviderCode,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> TestResultOut:
    with context.require_backend().transaction() as repos:
        service = context.ai_settings(repos)
        result = service.test_connection(principal.user, code, ip=client_ip(request))
        view = next(v for v in service.overview(principal.user) if v.provider.code is code)
        provider = _provider_out(repos, view)
    return TestResultOut(
        ok=result.ok, error=result.error, models_found=result.models_found, provider=provider
    )


@router.put(
    "/providers/{code}", response_model=ProviderOut, summary="Habilita y fija el límite mensual"
)
def update_provider(
    code: ProviderCode,
    body: ProviderSettingsIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> ProviderOut:
    with context.require_backend().transaction() as repos:
        view = context.ai_settings(repos).update_provider(
            principal.user,
            code,
            enabled=body.enabled,
            monthly_limit_usd=body.monthly_limit_usd,
            ip=client_ip(request),
        )
        return _provider_out(repos, view)


@router.get(
    "/models", response_model=list[ModelOut], summary="Modelos que informan los proveedores"
)
def list_models(
    provider: ProviderCode | None = Query(default=None),  # noqa: B008
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> list[ModelOut]:
    with context.require_backend().transaction() as repos:
        models = context.ai_settings(repos).models(principal.user, provider)
    return [ModelOut.of(model) for model in models]


@router.get("/assignments", response_model=list[AssignmentOut], summary="Modelo de cada operación")
def list_assignments(
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> list[AssignmentOut]:
    with context.require_backend().transaction() as repos:
        pairs = context.ai_settings(repos).assignments(principal.user)
    return [AssignmentOut.of(assignment, model) for assignment, model in pairs]


@router.put("/assignments/{operation}", response_model=AssignmentOut, summary="Asigna un modelo")
def assign_model(
    operation: Operation,
    body: AssignmentIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> AssignmentOut:
    with context.require_backend().transaction() as repos:
        assignment, model = context.ai_settings(repos).assign(
            principal.user, operation, body.model_id, ip=client_ip(request)
        )
    return AssignmentOut.of(assignment, model)
