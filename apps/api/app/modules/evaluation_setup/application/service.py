"""Perfil de puesto y prompt de evaluación: reglas y permisos.

Permisos (decisión 10 de la arquitectura): quien tiene acceso de lectura a la
vacante consulta; quien colabora edita el perfil y los borradores y los envía a
revisión; solo el responsable o un administrador aprueba o archiva.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from app.core.exceptions.errors import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.ids import new_sequential_uuid
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction, AuditResult
from app.modules.evaluation_setup.domain import assistant, generator
from app.modules.evaluation_setup.domain.company_format import parse_profile_format
from app.modules.evaluation_setup.domain.models import (
    EvaluationSetupRepository,
    ProfileContent,
    ProfileOrigin,
    ProfileVersion,
    PromptStatus,
    PromptVersion,
)
from app.modules.evaluation_setup.domain.ports import (
    PROFILE_ANALYSIS,
    PROMPT_GENERATION,
    Assistant,
    AssistantAnswer,
    ProfileSourceError,
    ProfileSources,
)
from app.modules.vacancies.application.access import VacancyAccess
from app.modules.vacancies.domain.models import AccessLevel, UserInfo


@dataclass(frozen=True)
class ProfileProposal:
    """Perfil propuesto, leído del formato de la empresa o por la IA. No está
    guardado: la persona lo revisa. Si la IA falló, ``error`` lo explica y
    ``content`` va vacío."""

    content: ProfileContent | None
    truncated: bool
    source_file_id: uuid.UUID | None
    error: str | None = None
    # Cómo se obtuvo: del formato en Excel (sin IA) o con IA.
    origin: ProfileOrigin = ProfileOrigin.IA
    # Avisos para quien revisa (por ejemplo, datos del formato que no se copiaron).
    notices: tuple[str, ...] = ()


@dataclass(frozen=True)
class CriteriaProposal:
    suggestions: assistant.CriteriaSuggestions | None
    error: str | None = None


_NO_ASSISTANT = "La ayuda de IA no está disponible en esta instalación."
_BAD_ANSWER = "La IA no devolvió una propuesta utilizable. Inténtalo de nuevo o captúralo a mano."


class EvaluationSetupService:
    def __init__(
        self,
        repository: EvaluationSetupRepository,
        access: VacancyAccess,
        audit: AuditLog,
        clock: Callable[[], datetime],
        *,
        assistant_port: Assistant | None = None,
        sources: ProfileSources | None = None,
    ) -> None:
        self._repo = repository
        self._access = access
        self._audit = audit
        self._clock = clock
        self._assistant = assistant_port
        self._sources = sources

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
        origin: ProfileOrigin = ProfileOrigin.MANUAL,
        source_file_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> ProfileVersion:
        """Guarda el perfil como una versión nueva. Las anteriores no cambian.

        ``origin`` indica de dónde partió la persona: de una propuesta de la IA,
        de la lectura del formato de la empresa o de nada (captura manual). En
        todos los casos la revisó antes de guardar. ``source_file_id`` es el
        documento del que salió la propuesta, si lo hubo."""
        self._access.require(actor, vacancy_id, AccessLevel.COLABORACION)
        if source_file_id is not None and (
            self._sources is None
            or not self._sources.is_profile_document(vacancy_id, source_file_id)
        ):
            raise ValidationFailedError("El documento de origen no es un perfil de esta vacante.")
        if origin is ProfileOrigin.FORMATO and source_file_id is None:
            raise ValidationFailedError("Indica de qué documento se leyó el formato del perfil.")
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
            origin=origin,
            content=content,
            change_note=" ".join((change_note or "").split())[:300] or None,
            source_file_id=source_file_id,
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
            details={"version": version.version_number, "origen": version.origin.value},
        )
        return version

    # --- Ayudas de IA --------------------------------------------------------------------

    def _ask(
        self,
        operation: str,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        *,
        system: str,
        user: str,
        carries_document: bool,
    ) -> AssistantAnswer:
        if self._assistant is None:
            raise ServiceUnavailableError(_NO_ASSISTANT)
        return self._assistant.ask(
            operation,
            system=system,
            user=user,
            vacancy_id=vacancy_id,
            actor_user_id=actor.id,
            carries_document=carries_document,
        )

    def extract_profile(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        *,
        file_id: uuid.UUID | None = None,
        text: str | None = None,
        ip: str | None = None,
    ) -> ProfileProposal:
        """Lee un perfil (documento de la vacante o texto pegado) y lo devuelve
        como propuesta. No guarda ninguna versión.

        Si el documento es el formato de la empresa en Excel, se lee directamente
        de sus celdas, sin IA. En cualquier otro caso se pide a la IA."""
        self._access.require(actor, vacancy_id, AccessLevel.COLABORACION)
        if (file_id is None) == (text is None):
            raise ValidationFailedError("Elige un documento o pega el texto del perfil.")
        truncated = False
        if file_id is not None:
            if self._sources is None:
                raise ServiceUnavailableError(_NO_ASSISTANT)
            try:
                sheets = self._sources.read_sheets(vacancy_id, file_id)
                reading = next(
                    (found for sheet in sheets or () if (found := parse_profile_format(sheet))),
                    None,
                )
                if reading is not None:
                    self._audit.record(
                        AuditAction.PERFIL_LEIDO_DEL_FORMATO,
                        actor_user_id=actor.id,
                        resource_type="vacante",
                        resource_id=vacancy_id,
                        ip=ip,
                        details={"documento": str(file_id), "avisos": len(reading.notices)},
                    )
                    return ProfileProposal(
                        reading.content,
                        truncated=False,
                        source_file_id=file_id,
                        origin=ProfileOrigin.FORMATO,
                        notices=reading.notices,
                    )
                source, truncated = self._sources.read_text(vacancy_id, file_id)
            except ProfileSourceError as error:
                raise ValidationFailedError(str(error)) from error
        else:
            source = "\n".join(line.rstrip() for line in (text or "").strip().splitlines())
            if len(source) < assistant.MIN_SOURCE_CHARS:
                raise ValidationFailedError(
                    f"El texto es muy corto: pega al menos {assistant.MIN_SOURCE_CHARS} letras."
                )
            truncated = len(source) > assistant.MAX_SOURCE_CHARS
            source = source[: assistant.MAX_SOURCE_CHARS]
        answer = self._ask(
            PROFILE_ANALYSIS,
            actor,
            vacancy_id,
            system=assistant.PROFILE_SYSTEM,
            user=assistant.profile_request(source, truncated),
            # Fuera de producción, enviar documentos requiere autorización expresa.
            carries_document=True,
        )
        content, error = None, None
        if not answer.ok:
            error = answer.error or "El proveedor de IA no respondió."
        else:
            try:
                if not answer.complete:
                    raise assistant.InvalidAnswerError("Respuesta incompleta.")
                content = assistant.profile_from_answer(answer.text)
            except assistant.InvalidAnswerError:
                error = _BAD_ANSWER
        self._audit.record(
            AuditAction.PERFIL_EXTRAIDO_CON_IA,
            result=AuditResult.PERMITIDO if content else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy_id,
            ip=ip,
            details={
                "origen": "documento" if file_id else "texto",
                "documento": str(file_id or ""),
            },
        )
        return ProfileProposal(content, truncated, file_id, error)

    def propose_criteria(
        self, actor: UserInfo, version_id: uuid.UUID, *, ip: str | None = None
    ) -> CriteriaProposal:
        """Pide a la IA una mejor redacción de los criterios de un borrador. No
        guarda nada y no puede añadir criterios ni requisitos."""
        version = self._load(actor, version_id, AccessLevel.COLABORACION)
        if version.status is not PromptStatus.BORRADOR:
            raise ConflictError("Solo se proponen mejoras sobre un borrador.")
        if not version.criteria:
            raise ValidationFailedError("La rúbrica no tiene criterios que mejorar.")
        profile = self._repo.profile_version(version.profile_version_id)
        if profile is None:
            raise NotFoundError("El perfil del que salió este prompt ya no existe.")
        answer = self._ask(
            PROMPT_GENERATION,
            actor,
            version.vacancy_id,
            system=assistant.CRITERIA_SYSTEM,
            user=assistant.criteria_request(profile.content, version.criteria),
            carries_document=False,
        )
        suggestions, error = None, None
        if not answer.ok:
            error = answer.error or "El proveedor de IA no respondió."
        else:
            try:
                if not answer.complete:
                    raise assistant.InvalidAnswerError("Respuesta incompleta.")
                suggestions = assistant.criteria_from_answer(answer.text, version.criteria)
            except assistant.InvalidAnswerError:
                error = _BAD_ANSWER
        self._audit.record(
            AuditAction.PROMPT_CRITERIOS_PROPUESTOS,
            result=AuditResult.PERMITIDO if suggestions else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type="prompt",
            resource_id=version.id,
            ip=ip,
            details={
                "vacante": str(version.vacancy_id),
                "criterios": len(suggestions.suggestions) if suggestions else 0,
            },
        )
        return CriteriaProposal(suggestions, error)

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
