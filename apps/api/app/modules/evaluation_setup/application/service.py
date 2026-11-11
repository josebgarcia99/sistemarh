"""Perfil de puesto y prompt de evaluación: reglas y permisos.

Permisos (decisión 10 de la arquitectura): quien tiene acceso de lectura a la
vacante consulta; quien colabora edita el perfil y los borradores y los envía a
revisión; solo el responsable o un administrador aprueba o archiva.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from app.core.exceptions.errors import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_sequential_uuid
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction
from app.modules.evaluation_setup.domain import generator
from app.modules.evaluation_setup.domain.models import (
    EvaluationSetupRepository,
    ProfileOrigin,
    ProfileVersion,
    PromptStatus,
    PromptVersion,
)
from app.modules.vacancies.application.access import VacancyAccess
from app.modules.vacancies.domain.models import AccessLevel, UserInfo


class EvaluationSetupService:
    def __init__(
        self,
        repository: EvaluationSetupRepository,
        access: VacancyAccess,
        audit: AuditLog,
        clock: Callable[[], datetime],
    ) -> None:
        self._repo = repository
        self._access = access
        self._audit = audit
        self._clock = clock

    # --- Perfil --------------------------------------------------------------------------

    def profile_versions(self, actor: UserInfo, vacancy_id: uuid.UUID) -> list[ProfileVersion]:
        self._access.require(actor, vacancy_id, AccessLevel.LECTURA)
        return self._repo.profile_versions(vacancy_id)

    def save_profile(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        data: dict[str, object],
        *,
        change_note: str | None,
        expected_version: int,
        ip: str | None = None,
    ) -> ProfileVersion:
        """Guarda el perfil como una versión nueva. Las anteriores no cambian."""
        self._access.require(actor, vacancy_id, AccessLevel.COLABORACION)
        try:
            content = generator.validate_profile(data)
        except generator.SetupValidationError as error:
            raise ValidationFailedError(str(error)) from error
        versions = self._repo.profile_versions(vacancy_id)
        latest = versions[0].version_number if versions else 0
        if expected_version != latest:
            raise ConflictError(
                "Otra persona guardó una versión más reciente del perfil. Vuelve a cargarlo."
            )
        if versions and versions[0].content == content:
            raise ValidationFailedError("El perfil no tiene cambios respecto a la versión actual.")
        version = ProfileVersion(
            id=new_sequential_uuid(),
            vacancy_id=vacancy_id,
            version_number=latest + 1,
            origin=ProfileOrigin.MANUAL,
            content=content,
            change_note=" ".join((change_note or "").split())[:300] or None,
            source_file_id=None,
            created_at=self._clock(),
            created_by=actor.id,
        )
        self._repo.add_profile_version(version)
        self._audit.record(
            AuditAction.PERFIL_VERSION_CREADA,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy_id,
            ip=ip,
            details={"version": version.version_number},
        )
        return version

    # --- Prompts: consulta ---------------------------------------------------------------

    def prompt_versions(self, actor: UserInfo, vacancy_id: uuid.UUID) -> list[PromptVersion]:
        self._access.require(actor, vacancy_id, AccessLevel.LECTURA)
        return [self._with_issues(version) for version in self._repo.prompt_versions(vacancy_id)]

    @staticmethod
    def _with_issues(version: PromptVersion) -> PromptVersion:
        version.issues = (
            generator.review_issues(version)
            if version.status in (PromptStatus.BORRADOR, PromptStatus.EN_REVISION)
            else []
        )
        return version

    def _load(self, actor: UserInfo, version_id: uuid.UUID, minimum: AccessLevel) -> PromptVersion:
        version = self._repo.prompt_version(version_id)
        if version is None:
            raise NotFoundError("La versión del prompt no existe.")
        self._access.require(actor, version.vacancy_id, minimum)
        return version

    def prompt_version(self, actor: UserInfo, version_id: uuid.UUID) -> PromptVersion:
        return self._with_issues(self._load(actor, version_id, AccessLevel.LECTURA))

    def approved_prompt(self, vacancy_id: uuid.UUID) -> PromptVersion | None:
        """La versión aprobada más reciente: la única con la que se evalúan CV."""
        for version in self._repo.prompt_versions(vacancy_id):
            if version.status is PromptStatus.APROBADO:
                return version
        return None

    # --- Prompts: cambios ----------------------------------------------------------------

    def _next_number(self, vacancy_id: uuid.UUID) -> int:
        versions = self._repo.prompt_versions(vacancy_id)
        return versions[0].version_number + 1 if versions else 1

    def _record(
        self, action: AuditAction, actor: UserInfo, version: PromptVersion, ip: str | None
    ) -> None:
        self._audit.record(
            action,
            actor_user_id=actor.id,
            resource_type="prompt",
            resource_id=version.id,
            ip=ip,
            details={
                "vacante": str(version.vacancy_id),
                "version": version.version_number,
                "estado": version.status.value,
            },
        )

    def generate(
        self, actor: UserInfo, vacancy_id: uuid.UUID, *, ip: str | None = None
    ) -> PromptVersion:
        """Crea un borrador a partir del perfil vigente. No inventa requisitos."""
        self._access.require(actor, vacancy_id, AccessLevel.COLABORACION)
        profiles = self._repo.profile_versions(vacancy_id)
        if not profiles:
            raise ValidationFailedError("Primero guarda el perfil de puesto de la vacante.")
        profile = profiles[0]
        now = self._clock()
        criteria = generator.criteria_from_profile(profile.content, new_sequential_uuid)
        version = PromptVersion(
            id=new_sequential_uuid(),
            vacancy_id=vacancy_id,
            version_number=self._next_number(vacancy_id),
            status=PromptStatus.BORRADOR,
            profile_version_id=profile.id,
            pass_threshold=generator.DEFAULT_THRESHOLD,
            layers=generator.build_layers(profile.content, criteria, generator.DEFAULT_THRESHOLD),
            criteria=criteria,
            created_at=now,
            created_by=actor.id,
            updated_at=now,
            updated_by=actor.id,
        )
        self._repo.add_prompt_version(version)
        self._record(AuditAction.PROMPT_GENERADO, actor, version, ip)
        return self._with_issues(version)

    def _save(self, version: PromptVersion, actor: UserInfo, expected_revision: int) -> None:
        version.updated_at = self._clock()
        version.updated_by = actor.id
        version.revision = expected_revision + 1
        if not self._repo.save_prompt_version(version, expected_revision=expected_revision):
            raise ConflictError("Otra persona modificó esta versión. Vuelve a cargarla.")

    def update_draft(
        self,
        actor: UserInfo,
        version_id: uuid.UUID,
        *,
        layers: dict[str, object],
        criteria: list[dict[str, object]],
        pass_threshold: Decimal,
        expected_revision: int,
        ip: str | None = None,
    ) -> PromptVersion:
        version = self._load(actor, version_id, AccessLevel.COLABORACION)
        if version.status is not PromptStatus.BORRADOR:
            raise ConflictError(
                "Solo se edita un borrador. Una versión aprobada no cambia: duplícala "
                "para crear una nueva."
            )
        try:
            generator.apply_edit(
                version,
                layers=layers,
                criteria=criteria,
                pass_threshold=pass_threshold,
                new_id=new_sequential_uuid,
            )
        except generator.SetupValidationError as error:
            raise ValidationFailedError(str(error)) from error
        self._save(version, actor, expected_revision)
        self._record(AuditAction.PROMPT_EDITADO, actor, version, ip)
        return self._with_issues(version)

    def _transition(
        self,
        actor: UserInfo,
        version_id: uuid.UUID,
        *,
        allowed_from: tuple[PromptStatus, ...],
        to: PromptStatus,
        minimum: AccessLevel,
        action: AuditAction,
        expected_revision: int,
        ip: str | None,
        must_be_ready: bool = False,
    ) -> PromptVersion:
        version = self._load(actor, version_id, minimum)
        if version.status not in allowed_from:
            raise ConflictError("Esta versión no admite ese cambio en su estado actual.")
        if must_be_ready:
            issues = generator.review_issues(version)
            if issues:
                raise ValidationFailedError("El prompt aún no está listo: " + " ".join(issues))
        now = self._clock()
        version.status = to
        if to is PromptStatus.EN_REVISION:
            version.submitted_at, version.submitted_by = now, actor.id
        elif to is PromptStatus.APROBADO:
            version.approved_at, version.approved_by = now, actor.id
        elif to is PromptStatus.ARCHIVADO:
            version.archived_at, version.archived_by = now, actor.id
        self._save(version, actor, expected_revision)
        self._record(action, actor, version, ip)
        return self._with_issues(version)

    def submit(self, actor: UserInfo, version_id: uuid.UUID, *, expected_revision: int, ip=None):
        return self._transition(
            actor,
            version_id,
            allowed_from=(PromptStatus.BORRADOR,),
            to=PromptStatus.EN_REVISION,
            minimum=AccessLevel.COLABORACION,
            action=AuditAction.PROMPT_ENVIADO_A_REVISION,
            expected_revision=expected_revision,
            ip=ip,
            must_be_ready=True,
        )

    def return_to_draft(
        self, actor: UserInfo, version_id: uuid.UUID, *, expected_revision: int, ip=None
    ):
        return self._transition(
            actor,
            version_id,
            allowed_from=(PromptStatus.EN_REVISION,),
            to=PromptStatus.BORRADOR,
            minimum=AccessLevel.COLABORACION,
            action=AuditAction.PROMPT_DEVUELTO,
            expected_revision=expected_revision,
            ip=ip,
        )

    def approve(self, actor: UserInfo, version_id: uuid.UUID, *, expected_revision: int, ip=None):
        return self._transition(
            actor,
            version_id,
            allowed_from=(PromptStatus.EN_REVISION,),
            to=PromptStatus.APROBADO,
            minimum=AccessLevel.RESPONSABLE,
            action=AuditAction.PROMPT_APROBADO,
            expected_revision=expected_revision,
            ip=ip,
            must_be_ready=True,
        )

    def archive(self, actor: UserInfo, version_id: uuid.UUID, *, expected_revision: int, ip=None):
        return self._transition(
            actor,
            version_id,
            allowed_from=(PromptStatus.BORRADOR, PromptStatus.EN_REVISION, PromptStatus.APROBADO),
            to=PromptStatus.ARCHIVADO,
            minimum=AccessLevel.RESPONSABLE,
            action=AuditAction.PROMPT_ARCHIVADO,
            expected_revision=expected_revision,
            ip=ip,
        )

    def duplicate(
        self, actor: UserInfo, version_id: uuid.UUID, *, ip: str | None = None
    ) -> PromptVersion:
        """Copia una versión (aprobada o no) como borrador nuevo."""
        source = self._load(actor, version_id, AccessLevel.COLABORACION)
        now = self._clock()
        copy = PromptVersion(
            id=new_sequential_uuid(),
            vacancy_id=source.vacancy_id,
            version_number=self._next_number(source.vacancy_id),
            status=PromptStatus.BORRADOR,
            profile_version_id=source.profile_version_id,
            pass_threshold=source.pass_threshold,
            layers=dict(source.layers),
            criteria=[replace(c, id=new_sequential_uuid()) for c in source.criteria],
            created_at=now,
            created_by=actor.id,
            updated_at=now,
            updated_by=actor.id,
            duplicated_from=source.id,
        )
        self._repo.add_prompt_version(copy)
        self._record(AuditAction.PROMPT_DUPLICADO, actor, copy, ip)
        return self._with_issues(copy)
