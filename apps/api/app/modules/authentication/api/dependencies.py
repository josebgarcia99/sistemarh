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
from app.core.middleware.correlation import route_template
from app.modules.authentication.domain.models import AuthSession
from app.modules.users.domain.models import User

SESSION_COOKIE = "reclu_session"
CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Principal:
    user: User
    session: AuthSession


API_PREFIX = "/api/v1"
# Lo único que puede usar un analista de estudios socioeconómicos. Se compara la
# ruta declarada, no la dirección: una ruta nueva queda cerrada hasta añadirla aquí.
STUDY_ANALYST_ROUTES = frozenset(
    {
        ("GET", "/auth/me"),
        ("POST", "/auth/logout"),
        ("GET", "/study-queue"),
        ("GET", "/applications/{application_id}/assessments"),
        ("POST", "/applications/{application_id}/assessments"),
        ("GET", "/assessments/{assessment_id}"),
        ("PUT", "/assessments/{assessment_id}"),
        ("POST", "/assessments/{assessment_id}/digitization"),
        ("POST", "/assessments/{assessment_id}/photo-descriptions"),
        ("GET", "/form-templates"),
        ("GET", "/vacancies/{vacancy_id}/files"),
        ("POST", "/vacancies/{vacancy_id}/files"),
        ("GET", "/files/{file_id}"),
        ("GET", "/files/{file_id}/download"),
    }
)


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
    if user.is_study_analyst:
        route = (request.method, route_template(request.scope).removeprefix(API_PREFIX))
        if route not in STUDY_ANALYST_ROUTES:
            # Todo lo que no está en la lista queda cerrado para este puesto.
            raise PermissionDeniedError("Tu puesto solo da acceso a los estudios socioeconómicos.")
    return Principal(user=user, session=session)


def require_admin(
    principal: Principal = Depends(require_user),  # noqa: B008
) -> Principal:
    if not principal.user.is_admin:
        # El rechazo se audita de forma central (``composition.denials``).
        raise PermissionDeniedError("Esta operación es solo para administradores.")
    return principal
