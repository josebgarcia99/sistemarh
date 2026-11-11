"""Vacantes y compartición.

Las rutas exigen sesión; el acceso a cada vacante lo decide
``VacancyAccess`` dentro del servicio, sobre el objeto concreto.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.composition.context import AppContext, client_ip, get_context
from app.modules.authentication.api.dependencies import Principal, require_user
from app.modules.vacancies.api.schemas import (
    MemberIn,
    MemberOut,
    SensitiveGrantsIn,
    SensitiveGrantsOut,
    StatusChangeIn,
    VacancyIn,
    VacancyOut,
    VacancyPage,
    VacancyUpdateIn,
)
from app.modules.vacancies.domain.models import Scope, VacancyStatus

router = APIRouter(prefix="/vacancies", tags=["vacantes"])


@router.get("", response_model=VacancyPage, summary="Vacantes que el usuario puede ver")
def list_vacancies(
    scope: Scope = Query(default=Scope.ALL),  # noqa: B008
    status_filter: VacancyStatus | None = Query(default=None, alias="status"),  # noqa: B008
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> VacancyPage:
    with context.require_backend().transaction() as repos:
        views, total = context.vacancy_service(repos).list(
            principal.user,
            scope=scope,
            status=status_filter,
            search=search,
            page=page,
            page_size=page_size,
        )
    return VacancyPage(
        items=[VacancyOut.from_view(v) for v in views], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=VacancyOut, status_code=status.HTTP_201_CREATED, summary="Alta")
def create_vacancy(
    body: VacancyIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> VacancyOut:
    with context.require_backend().transaction() as repos:
        view = context.vacancy_service(repos).create(
            principal.user, body.to_data(), ip=client_ip(request)
        )
    return VacancyOut.from_view(view)


@router.get("/{vacancy_id}", response_model=VacancyOut, summary="Detalle")
def get_vacancy(
    vacancy_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> VacancyOut:
    with context.require_backend().transaction() as repos:
        return VacancyOut.from_view(context.vacancy_service(repos).get(principal.user, vacancy_id))


@router.put("/{vacancy_id}", response_model=VacancyOut, summary="Editar datos")
def update_vacancy(
    vacancy_id: uuid.UUID,
    body: VacancyUpdateIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> VacancyOut:
    data = VacancyIn(**body.model_dump(exclude={"version"})).to_data()
    with context.require_backend().transaction() as repos:
        view = context.vacancy_service(repos).update(
            principal.user,
            vacancy_id,
            data,
            expected_version=body.version,
            ip=client_ip(request),
        )
    return VacancyOut.from_view(view)


@router.post("/{vacancy_id}/status", response_model=VacancyOut, summary="Cambiar estado")
def change_status(
    vacancy_id: uuid.UUID,
    body: StatusChangeIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> VacancyOut:
    with context.require_backend().transaction() as repos:
        view = context.vacancy_service(repos).change_status(
            principal.user,
            vacancy_id,
            body.status,
            expected_version=body.version,
            ip=client_ip(request),
        )
    return VacancyOut.from_view(view)


@router.get(
    "/{vacancy_id}/members", response_model=list[MemberOut], summary="Con quién está compartida"
)
def list_members(
    vacancy_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> list[MemberOut]:
    with context.require_backend().transaction() as repos:
        views = context.vacancy_service(repos).members(principal.user, vacancy_id)
    return [MemberOut.from_view(view) for view in views]


@router.put(
    "/{vacancy_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Compartir o cambiar el tipo de acceso",
)
def set_member(
    vacancy_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> None:
    with context.require_backend().transaction() as repos:
        context.vacancy_service(repos).set_member(
            principal.user, vacancy_id, user_id, body.access_type, ip=client_ip(request)
        )


@router.delete(
    "/{vacancy_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revocar el acceso",
)
def revoke_member(
    vacancy_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> None:
    with context.require_backend().transaction() as repos:
        context.vacancy_service(repos).revoke_member(
            principal.user, vacancy_id, user_id, ip=client_ip(request)
        )


@router.put(
    "/{vacancy_id}/members/{user_id}/sensitive-grants",
    response_model=SensitiveGrantsOut,
    summary="Permisos adicionales para documentos sensibles",
)
def set_sensitive_grants(
    vacancy_id: uuid.UUID,
    user_id: uuid.UUID,
    body: SensitiveGrantsIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> SensitiveGrantsOut:
    with context.require_backend().transaction() as repos:
        classes = context.vacancy_service(repos).set_sensitive_grants(
            principal.user,
            vacancy_id,
            user_id,
            set(body.document_classes),
            ip=client_ip(request),
        )
    return SensitiveGrantsOut(document_classes=classes)
