"""Acceso a los documentos de una vacante.

Une el módulo de documentos, que no conoce las reglas de reclutamiento, con la
autorización por vacante. El permiso se evalúa en el momento de cada consulta
o descarga: revocar un acceso bloquea también los documentos ya cargados.
"""

from __future__ import annotations

import uuid

from app.core.exceptions.errors import NotFoundError, PermissionDeniedError
from app.modules.file_management.domain.models import Actor
from app.modules.vacancies.application.access import VacancyAccess
from app.modules.vacancies.domain.models import AccessLevel, SensitiveClass, VacancyRepository

_ALL_CLASSES = frozenset(item.value for item in SensitiveClass)
STUDY_CLASS = SensitiveClass.ESTUDIO_SOCIOECONOMICO.value
_ANALYST_ONLY = "Tu puesto solo da acceso a los estudios socioeconómicos."


def is_study_analyst(actor: object) -> bool:
    """Analista de estudios socioeconómicos: trabaja los estudios de cualquier
    vacante y nada más."""
    return getattr(actor, "is_study_analyst", False) is True


class VacancyFileAccessPolicy:
    def __init__(self, vacancies: VacancyRepository) -> None:
        self._vacancies = vacancies
        self._access = VacancyAccess(vacancies)

    def _granted(self, actor: Actor, vacancy_id: uuid.UUID, level: AccessLevel) -> frozenset[str]:
        # El responsable y el administrador no necesitan el permiso adicional.
        if level >= AccessLevel.RESPONSABLE:
            return _ALL_CLASSES
        grants = self._vacancies.active_grants(vacancy_id=vacancy_id, user_id=actor.id)
        return frozenset(grant.document_class.value for grant in grants)

    def _require(
        self,
        actor: Actor,
        vacancy_id: uuid.UUID,
        minimum: AccessLevel,
        sensitive_class: str | None,
    ) -> None:
        if is_study_analyst(actor):
            # No depende de que le compartan la vacante: su acceso es por puesto y
            # se limita a lo clasificado como estudio socioeconómico.
            self._existing(vacancy_id)
            if sensitive_class != STUDY_CLASS:
                raise PermissionDeniedError(_ANALYST_ONLY)
            return
        _, level = self._access.require(actor, vacancy_id, minimum)  # type: ignore[arg-type]
        if sensitive_class is not None and sensitive_class not in self._granted(
            actor, vacancy_id, level
        ):
            raise PermissionDeniedError(
                "Este documento es sensible y requiere un permiso adicional sobre la vacante."
            )

    def require_read(
        self, actor: Actor, vacancy_id: uuid.UUID, sensitive_class: str | None
    ) -> None:
        self._require(actor, vacancy_id, AccessLevel.LECTURA, sensitive_class)

    def require_write(
        self, actor: Actor, vacancy_id: uuid.UUID, sensitive_class: str | None
    ) -> None:
        self._require(actor, vacancy_id, AccessLevel.COLABORACION, sensitive_class)

    def _existing(self, vacancy_id: uuid.UUID) -> None:
        if self._vacancies.get(vacancy_id) is None:
            raise NotFoundError("La vacante no existe.")

    def readable_sensitive_classes(self, actor: Actor, vacancy_id: uuid.UUID) -> frozenset[str]:
        if is_study_analyst(actor):
            self._existing(vacancy_id)
            return frozenset({STUDY_CLASS})
        _, level = self._access.require(actor, vacancy_id, AccessLevel.LECTURA)  # type: ignore[arg-type]
        return self._granted(actor, vacancy_id, level)
