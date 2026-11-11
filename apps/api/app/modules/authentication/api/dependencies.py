"""Dependencias de autenticación y autorización para las rutas.

Todo se deniega por omisión: una ruta solo es accesible sin sesión si no
declara ninguna de estas dependencias, y una prueba recorre todas las rutas
para comprobar que eso solo ocurre en las de la lista permitida.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import Depends, Request

from app.composition.context import AppContext, get_context
from app.core.exceptions.errors import CsrfError, PermissionDeniedError
from app.modules.authentication.domain.models import AuthSession
from app.modules.users.domain.models import User

SESSION_COOKIE = "reclu_session"
CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Principal:
    user: User
    session: AuthSession


def require_user(
    request: Request,
    context: AppContext = Depends(get_context),  # noqa: B008
) -> Principal:
    """Exige una sesión válida y, en operaciones que modifican, el token CSRF."""
    with context.require_backend().transaction() as repos:
        session, user = context.auth_service(repos).resolve(request.cookies.get(SESSION_COOKIE))
    if request.method not in _SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not secrets.compare_digest(sent, session.csrf_token):
            raise CsrfError("Falta el token de verificación o no coincide.")
    # Queda disponible para auditar un rechazo posterior de esta solicitud.
    request.state.user_id = user.id
    return Principal(user=user, session=session)


def require_admin(
    principal: Principal = Depends(require_user),  # noqa: B008
) -> Principal:
    if not principal.user.is_admin:
        # El rechazo se audita de forma central (``composition.denials``).
        raise PermissionDeniedError("Esta operación es solo para administradores.")
    return principal
