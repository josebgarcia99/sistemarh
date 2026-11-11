"""Administración de usuarios. Todas las rutas son solo para administradores."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.composition.context import AppContext, client_ip, get_context
from app.modules.authentication.api.dependencies import Principal, require_admin
from app.modules.users.api.schemas import (
    PasswordResetIn,
    PasswordResetOut,
    UserCreateIn,
    UserOut,
    UserPage,
    UserUpdateIn,
)

router = APIRouter(prefix="/users", tags=["usuarios"])


@router.get("", response_model=UserPage, summary="Lista de usuarios")
def list_users(
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> UserPage:
    with context.require_backend().transaction() as repos:
        users, total = context.user_service(repos).list(
            search=search, page=page, page_size=page_size
        )
    return UserPage(
        items=[UserOut.from_domain(u) for u in users], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Alta")
def create_user(
    body: UserCreateIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> UserOut:
    with context.require_backend().transaction() as repos:
        user = context.user_service(repos).create_user(
            principal.user,
            email=body.email,
            full_name=body.full_name,
            password=body.password,
            role=body.role,
            ip=client_ip(request),
        )
    return UserOut.from_domain(user)


@router.get("/{user_id}", response_model=UserOut, summary="Detalle")
def get_user(
    user_id: uuid.UUID,
    _: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> UserOut:
    with context.require_backend().transaction() as repos:
        return UserOut.from_domain(context.user_service(repos).get(user_id))


@router.patch("/{user_id}", response_model=UserOut, summary="Editar nombre o rol")
def update_user(
    user_id: uuid.UUID,
    body: UserUpdateIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> UserOut:
    with context.require_backend().transaction() as repos:
        user = context.user_service(repos).update(
            principal.user,
            user_id,
            full_name=body.full_name,
            role=body.role,
            ip=client_ip(request),
        )
    return UserOut.from_domain(user)


@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetOut,
    summary="Restablecer contraseña y cerrar sus sesiones",
)
def reset_password(
    user_id: uuid.UUID,
    body: PasswordResetIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> PasswordResetOut:
    with context.require_backend().transaction() as repos:
        closed = context.user_service(repos).reset_password(
            principal.user, user_id, new_password=body.new_password, ip=client_ip(request)
        )
    return PasswordResetOut(sessions_closed=closed)


@router.post("/{user_id}/deactivate", response_model=UserOut, summary="Dar de baja")
def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> UserOut:
    with context.require_backend().transaction() as repos:
        user = context.user_service(repos).deactivate(
            principal.user, user_id, ip=client_ip(request)
        )
    return UserOut.from_domain(user)


@router.post("/{user_id}/activate", response_model=UserOut, summary="Reactivar")
def activate_user(
    user_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> UserOut:
    with context.require_backend().transaction() as repos:
        user = context.user_service(repos).activate(principal.user, user_id, ip=client_ip(request))
    return UserOut.from_domain(user)
