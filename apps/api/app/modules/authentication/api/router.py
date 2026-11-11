"""Inicio y cierre de sesión."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.composition.context import AppContext, client_ip, get_context
from app.core.config.settings import Environment
from app.core.exceptions.errors import InvalidCredentialsError
from app.modules.authentication.api.dependencies import SESSION_COOKIE, Principal, require_user
from app.modules.users.api.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["sesión"])


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class SessionOut(BaseModel):
    user: UserOut
    # El frontend lo reenvía en la cabecera X-CSRF-Token al modificar datos.
    csrf_token: str


@router.post("/login", response_model=SessionOut, summary="Iniciar sesión")
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    context: AppContext = Depends(get_context),  # noqa: B008
) -> SessionOut:
    # La transacción se confirma también cuando las credenciales fallan, para
    # conservar el contador de intentos y el evento de auditoría.
    with context.require_backend().transaction() as repos:
        result = context.auth_service(repos).login(
            body.email,
            body.password,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    if result is None:
        raise InvalidCredentialsError()

    response.set_cookie(
        SESSION_COOKIE,
        result.token,
        httponly=True,
        # En desarrollo local no hay HTTPS; en cualquier otro entorno es obligatorio.
        secure=context.settings.environment is not Environment.DEVELOPMENT,
        samesite="lax",
        path="/",
        max_age=int(context.auth_policy.absolute_timeout.total_seconds()),
    )
    return SessionOut(user=UserOut.from_domain(result.user), csrf_token=result.session.csrf_token)


@router.get("/me", response_model=SessionOut, summary="Sesión actual")
def me(principal: Principal = Depends(require_user)) -> SessionOut:  # noqa: B008
    return SessionOut(
        user=UserOut.from_domain(principal.user), csrf_token=principal.session.csrf_token
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesión")
def logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> None:
    with context.require_backend().transaction() as repos:
        context.auth_service(repos).logout(principal.session, ip=client_ip(request))
    response.delete_cookie(SESSION_COOKIE, path="/")
