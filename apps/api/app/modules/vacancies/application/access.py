"""Autorización por vacante. Es el único lugar donde se decide el acceso.

Regla general: se deniega todo salvo lo que aquí se concede.

- Administrador: acceso total.
- Responsable principal: acceso total a su vacante, salvo transferirla.
- Colaboración: opera el proceso; no edita la vacante ni la comparte.
- Lectura: solo consulta.

Si el usuario no tiene ningún acceso, la respuesta es "no encontrado", igual
que si la vacante no existiera: así no se revela que existe.
"""

from __future__ import annotations

import uuid

from app.core.exceptions.errors import NotFoundError, PermissionDeniedError
from app.modules.vacancies.domain.models import (
    AccessLevel,
    AccessType,
    UserInfo,
    Vacancy,
    VacancyRepository,
)

_MEMBER_LEVEL = {
    AccessType.LECTURA: AccessLevel.LECTURA,
    AccessType.COLABORACION: AccessLevel.COLABORACION,
}


def effective_access(
    user: UserInfo, vacancy: Vacancy, member_access: AccessType | None
) -> AccessLevel | None:
    if user.is_admin:
        return AccessLevel.ADMINISTRADOR
    if vacancy.owner_user_id == user.id:
        return AccessLevel.RESPONSABLE
    if member_access is not None:
        return _MEMBER_LEVEL[member_access]
    return None


class VacancyAccess:
    def __init__(self, vacancies: VacancyRepository) -> None:
        self._vacancies = vacancies

    def require(
        self, user: UserInfo, vacancy_id: uuid.UUID, minimum: AccessLevel
    ) -> tuple[Vacancy, AccessLevel]:
        vacancy = self._vacancies.get(vacancy_id)
        if vacancy is None:
            raise NotFoundError("La vacante no existe.")
        member = None if user.is_admin else self._vacancies.active_member(vacancy_id, user.id)
        level = effective_access(user, vacancy, member.access_type if member else None)
        if level is None:
            raise NotFoundError("La vacante no existe.")
        if level < minimum:
            raise PermissionDeniedError("Tu acceso a esta vacante no permite esta operación.")
        return vacancy, level
