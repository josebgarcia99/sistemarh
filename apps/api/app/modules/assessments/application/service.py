"""Evaluaciones posteriores y síntesis del expediente: reglas y permisos.

Permisos: los de la vacante (lectura para consultar, colaboración para
capturar). La psicometría y el estudio socioeconómico exigen además el
permiso adicional por persona, igual que sus documentos; el responsable y el
administrador lo tienen siempre. Las plantillas de formulario las administra
el administrador.

Ninguna evaluación mueve de etapa a nadie ni cambia el estado de una
postulación: avanzar sigue siendo una decisión de RH, registrada aparte.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.exceptions.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.ids import new_sequential_uuid
from app.modules.assessments.domain import assistant, company_study_format, rules
from app.modules.assessments.domain.models import (
    SENSITIVE_KINDS,
    Actor,
    Applications,
    Assessment,
    AssessmentAccess,
    AssessmentRepository,
    Assistant,
    DocumentError,
    Documents,
    FormTemplate,
    FormTemplateVersion,
    Kind,
    Photo,
    PhotoNote,
    Synthesis,
)
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction, AuditResult

_BAD_ANSWER = "La IA no devolvió una respuesta utilizable. Inténtalo de nuevo."
_INITIAL_STATUS = {
    Kind.PSICOMETRIA: "PENDIENTE",
    Kind.ENTREVISTA: "PROGRAMADA",
    Kind.PRUEBA_TECNICA: "PENDIENTE",
    Kind.ESTUDIO_SOCIOECONOMICO: "PENDIENTE",
}


@dataclass(frozen=True)
class AssessmentList:
    items: list[Assessment]
    # Tipos que existen para la postulación pero que este usuario no puede ver.
    restricted: list[Kind]
    writable: frozenset[Kind]


@dataclass(frozen=True)
class AiOutcome:
    """Resultado de una ayuda de IA: el contenido o el motivo del fallo."""

    content: Any | None
    error: str | None = None


@dataclass(frozen=True)
class SynthesisView:
    latest: Synthesis | None
    total: int
    # Hay síntesis que incluyen psicometría y este usuario no tiene ese permiso.
    hidden: bool


class AssessmentService:
    def __init__(
        self,
        repo: AssessmentRepository,
        access: AssessmentAccess,
        applications: Applications,
        documents: Documents,
        ai: Assistant,
        audit: AuditLog,
        clock: Callable[[], datetime],
    ) -> None:
        self._repo = repo
        self._access = access
        self._applications = applications
        self._documents = documents
        self._ai = ai
        self._audit = audit
        self._clock = clock

    # --- Plantillas de formulario --------------------------------------------------------

    def _ensure_default_template(self) -> None:
        if self._repo.templates():
            return
        now = self._clock()
        template = FormTemplate(
            id=new_sequential_uuid(),
            name=company_study_format.FORMAT_NAME,
            description=company_study_format.FORMAT_DESCRIPTION,
            status="ACTIVA",
            created_at=now,
            updated_at=now,
        )
        self._repo.add_template(template)
        self._repo.add_template_version(
            FormTemplateVersion(
                id=new_sequential_uuid(),
                template_id=template.id,
                version_number=1,
                sections=rules.template_sections(company_study_format.COMPANY_STUDY_TEMPLATE),
                created_at=now,
                created_by=None,
            )
        )

    def templates(self) -> list[tuple[FormTemplate, FormTemplateVersion]]:
        self._ensure_default_template()
        return [
            (template, self._repo.template_versions(template.id)[0])
            for template in self._repo.templates()
        ]

    def save_template(
        self,
        actor: Actor,
        template_id: uuid.UUID | None,
        *,
        name: str,
        description: str | None,
        sections: list[dict[str, Any]],
        expected_version: int = 0,
        ip: str | None = None,
    ) -> tuple[FormTemplate, FormTemplateVersion]:
        """Crea una plantilla o guarda una versión nueva. Los estudios ya
        capturados conservan la versión con la que se hicieron."""
        if not actor.is_admin:
            raise PermissionDeniedError("Solo un administrador configura los formularios.")
        name = rules.line(name, 150)
        if len(name) < 3:
            raise ValidationFailedError("Escribe el nombre del formulario.")
        try:
            clean = rules.template_sections(sections)
        except rules.RuleError as error:
            raise ValidationFailedError(str(error)) from error
        now = self._clock()
        if template_id is None:
            template = FormTemplate(
                id=new_sequential_uuid(),
                name=name,
                description=rules.line(description, 500) or None,
                status="ACTIVA",
                created_at=now,
                updated_at=now,
            )
            self._repo.add_template(template)
            number, changed = 1, True
        else:
            found = self._repo.template(template_id)
            if found is None:
                raise NotFoundError("El formulario no existe.")
            template = found
            latest = self._repo.template_versions(template.id)[0]
            if expected_version != latest.version_number:
                raise ConflictError("Otra persona guardó una versión más reciente.")
            template.name = name
            template.description = rules.line(description, 500) or None
            template.updated_at = now
            self._repo.save_template(template)
            number, changed = latest.version_number + 1, clean != latest.sections
            if not changed:
                return template, latest
        version = FormTemplateVersion(
            id=new_sequential_uuid(),
            template_id=template.id,
            version_number=number,
            sections=clean,
            created_at=now,
            created_by=actor.id,
        )
        self._repo.add_template_version(version)
        self._audit.record(
            AuditAction.FORMULARIO_VERSION_CREADA,
            actor_user_id=actor.id,
            resource_type="formulario",
            resource_id=template.id,
            ip=ip,
            details={"version": number, "campos": len(version.fields)},
        )
        return template, version

    def set_template_archived(
        self, actor: Actor, template_id: uuid.UUID, archived: bool
    ) -> tuple[FormTemplate, FormTemplateVersion]:
        if not actor.is_admin:
            raise PermissionDeniedError("Solo un administrador configura los formularios.")
        template = self._repo.template(template_id)
        if template is None:
            raise NotFoundError("El formulario no existe.")
        template.status = "ARCHIVADA" if archived else "ACTIVA"
        template.updated_at = self._clock()
        self._repo.save_template(template)
        return template, self._repo.template_versions(template.id)[0]

    def template_version(self, version_id: uuid.UUID) -> FormTemplateVersion | None:
        return self._repo.template_version(version_id)

    # --- Evaluaciones: consulta ----------------------------------------------------------

    def _application(self, application_id: uuid.UUID):  # noqa: ANN202
        application = self._applications.get(application_id)
        if application is None:
            raise NotFoundError("La postulación no existe.")
        return application

    def for_application(self, actor: Actor, application_id: uuid.UUID) -> AssessmentList:
        application = self._application(application_id)
        readable = self._access.readable(actor, application.vacancy_id)
        items = self._repo.for_application(application_id)
        writable = set()
        for kind in readable:
            try:
                self._access.require(actor, application.vacancy_id, kind, write=True)
                writable.add(kind)
            except PermissionDeniedError:
                pass
        return AssessmentList(
            items=[item for item in items if item.kind in readable],
            restricted=sorted({item.kind for item in items if item.kind not in readable}),
            writable=frozenset(writable),
        )

    def _load(self, actor: Actor, assessment_id: uuid.UUID, *, write: bool) -> Assessment:
        assessment = self._repo.get(assessment_id)
        if assessment is None:
            raise NotFoundError("La evaluación no existe.")
        self._access.require(actor, assessment.vacancy_id, assessment.kind, write=write)
        return assessment

    def get(self, actor: Actor, assessment_id: uuid.UUID) -> Assessment:
        return self._load(actor, assessment_id, write=False)

    # --- Evaluaciones: captura -----------------------------------------------------------

    def _apply(
        self,
        assessment: Assessment,
        *,
        status: str,
        data: dict[str, Any],
        event_date: datetime | None,
        file_id: uuid.UUID | None,
    ) -> None:
        """Valida lo capturado según el tipo y lo deja en la evaluación."""
        kind = assessment.kind
        try:
            rules.check_status(kind, status)
            score = None
            if kind is Kind.PSICOMETRIA:
                clean = rules.psychometric(data, status)
            elif kind is Kind.ENTREVISTA:
                clean = rules.interview(data, status)
            elif kind is Kind.PRUEBA_TECNICA:
                clean, score = rules.technical(data, status)
            else:
                version = self._repo.template_version(assessment.template_version_id)  # type: ignore[arg-type]
                if version is None:
                    raise rules.RuleError("El formulario del estudio ya no existe.")
                clean = rules.study(data, status, version)
                for document_id in rules.document_field_ids(version, clean["answers"]):
                    if not self._documents.belongs(
                        assessment.vacancy_id, uuid.UUID(document_id), kind
                    ):
                        raise rules.RuleError(
                            "Un documento del formulario no es un estudio socioeconómico "
                            "de esta vacante."
                        )
        except rules.RuleError as error:
            raise ValidationFailedError(str(error)) from error
        if file_id is not None and not self._documents.belongs(
            assessment.vacancy_id, file_id, kind
        ):
            raise ValidationFailedError(
                "El documento no pertenece a esta vacante o no es del tipo que corresponde."
            )
        if event_date is not None and status in ("REALIZADA", "PRESENTADA", "VALIDADA"):
            if event_date > self._clock():
                raise ValidationFailedError("La fecha no puede ser futura si ya se realizó.")
        assessment.status = status
        assessment.data = clean
        assessment.score = score
        assessment.event_date = event_date
        assessment.file_id = file_id

    def create(
        self,
        actor: Actor,
        application_id: uuid.UUID,
        kind: Kind,
        *,
        status: str | None = None,
        data: dict[str, Any],
        event_date: datetime | None = None,
        file_id: uuid.UUID | None = None,
        template_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> Assessment:
        application = self._application(application_id)
        self._access.require(actor, application.vacancy_id, kind, write=True)
        if not application.active:
            raise ConflictError("La postulación no está activa.")
        template_version_id = None
        if kind is Kind.ESTUDIO_SOCIOECONOMICO:
            self._ensure_default_template()
            template = self._repo.template(template_id) if template_id else None
            if template is None or template.status != "ACTIVA":
                raise ValidationFailedError("Elige un formulario activo para el estudio.")
            template_version_id = self._repo.template_versions(template.id)[0].id
        now = self._clock()
        assessment = Assessment(
            id=new_sequential_uuid(),
            application_id=application.id,
            vacancy_id=application.vacancy_id,
            kind=kind,
            status=_INITIAL_STATUS[kind],
            data={},
            created_at=now,
            created_by=actor.id,
            updated_at=now,
            updated_by=actor.id,
            template_version_id=template_version_id,
        )
        self._apply(
            assessment,
            status=status or _INITIAL_STATUS[kind],
            data=data,
            event_date=event_date,
            file_id=file_id,
        )
        self._repo.add(assessment)
        self._record(AuditAction.EVALUACION_CREADA, actor, assessment, ip)
        return assessment

    def update(
        self,
        actor: Actor,
        assessment_id: uuid.UUID,
        *,
        status: str,
        data: dict[str, Any],
        event_date: datetime | None,
        file_id: uuid.UUID | None,
        expected_version: int,
        ip: str | None = None,
    ) -> Assessment:
        assessment = self._load(actor, assessment_id, write=True)
        previous = assessment.status
        self._apply(assessment, status=status, data=data, event_date=event_date, file_id=file_id)
        assessment.updated_at = self._clock()
        assessment.updated_by = actor.id
        assessment.version = expected_version + 1
        if not self._repo.save(assessment, expected_version=expected_version):
            raise ConflictError(
                "Otra persona guardó cambios en esta evaluación. Vuelve a cargarla."
            )
        self._record(
            AuditAction.EVALUACION_ACTUALIZADA,
            actor,
            assessment,
            ip,
            estado_anterior=previous,
        )
        return assessment

    def _record(self, action: AuditAction, actor: Actor, assessment: Assessment, ip, **extra):  # noqa: ANN001, ANN003, ANN202
        self._audit.record(
            action,
            actor_user_id=actor.id,
            resource_type="evaluacion",
            resource_id=assessment.id,
            ip=ip,
            # Nunca el contenido: solo de qué tipo es y en qué estado quedó.
            details={
                "vacante": str(assessment.vacancy_id),
                "postulacion": str(assessment.application_id),
                "tipo": assessment.kind.value,
                "estado": assessment.status,
                **extra,
            },
        )

    # --- Ayudas de IA --------------------------------------------------------------------

    def _ask(  # noqa: ANN202
        self,
        actor: Actor,
        vacancy_id: uuid.UUID,
        operation: str,
        system: str,
        user: str,
        photos: tuple[Photo, ...] = (),
    ):
        return self._ai.ask(
            operation,
            system=system,
            user=user,
            vacancy_id=vacancy_id,
            actor_user_id=actor.id,
            **({"photos": photos} if photos else {}),
        )

    @staticmethod
    def _outcome(answer, parse) -> AiOutcome:  # noqa: ANN001
        if not answer.ok:
            return AiOutcome(None, answer.error or "El proveedor de IA no respondió.")
        try:
            if not answer.complete:
                raise assistant.InvalidAnswerError("Respuesta incompleta.")
            return AiOutcome(parse(answer.text))
        except assistant.InvalidAnswerError:
            return AiOutcome(None, _BAD_ANSWER)

    def _document_text(self, assessment: Assessment) -> tuple[str, bool]:
        if assessment.file_id is None:
            raise ValidationFailedError("Adjunta primero el documento a la evaluación y guárdala.")
        try:
            return self._documents.read_text(assessment.vacancy_id, assessment.file_id)
        except DocumentError as error:
            raise ValidationFailedError(str(error)) from error

    def summarize(
        self, actor: Actor, assessment_id: uuid.UUID, *, ip: str | None = None
    ) -> tuple[Assessment, str | None]:
        """Pide a la IA un resumen de lo documentado. No concluye ni decide.
        Devuelve la evaluación y, si la IA falló, el motivo."""
        assessment = self._load(actor, assessment_id, write=True)
        kind = assessment.kind
        if kind is Kind.ESTUDIO_SOCIOECONOMICO:
            raise ValidationFailedError("Un estudio socioeconómico no se resume: se digitaliza.")
        if kind is Kind.PSICOMETRIA:
            system, operation = assistant.PSYCHOMETRIC_SYSTEM, assistant.TEST_SUMMARY
            user = assistant.document_request(*self._document_text(assessment))
        elif kind is Kind.PRUEBA_TECNICA:
            system, operation = assistant.TECHNICAL_SYSTEM, assistant.TEST_SUMMARY
            user = (
                assistant.document_request(*self._document_text(assessment))
                if assessment.file_id
                else assistant.captured_request(assessment)
            )
        else:
            system, operation = assistant.INTERVIEW_SYSTEM, assistant.INTERVIEW_ANALYSIS
            if not assessment.data.get("questions") and not assessment.data.get("feedback"):
                raise ValidationFailedError("Captura y guarda la entrevista antes de resumirla.")
            user = assistant.captured_request(assessment)
        answer = self._ask(actor, assessment.vacancy_id, operation, system, user)
        outcome = self._outcome(answer, lambda text: assistant.summary_from_answer(kind, text))
        if outcome.content is not None:
            assessment.ai_summary = outcome.content
            assessment.ai_summary_at = self._clock()
            assessment.ai_summary_by = actor.id
            expected = assessment.version
            assessment.version += 1
            if not self._repo.save(assessment, expected_version=expected):
                raise ConflictError("Otra persona guardó cambios en esta evaluación.")
        self._audit.record(
            AuditAction.EVALUACION_RESUMIDA,
            result=AuditResult.PERMITIDO if outcome.content else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type="evaluacion",
            resource_id=assessment.id,
            ip=ip,
            details={"vacante": str(assessment.vacancy_id), "tipo": kind.value},
        )
        return assessment, outcome.error

    def digitize(
        self, actor: Actor, assessment_id: uuid.UUID, file_id: uuid.UUID, *, ip: str | None = None
    ) -> AiOutcome:
        """Lee un formulario escaneado y propone valores para los campos. No
        guarda nada: una persona revisa, corrige y marca qué queda verificado."""
        assessment = self._load(actor, assessment_id, write=True)
        if assessment.kind is not Kind.ESTUDIO_SOCIOECONOMICO:
            raise ValidationFailedError("Solo se digitalizan estudios socioeconómicos.")
        version = self._repo.template_version(assessment.template_version_id)  # type: ignore[arg-type]
        if version is None:
            raise NotFoundError("El formulario del estudio ya no existe.")
        if not self._documents.belongs(assessment.vacancy_id, file_id, assessment.kind):
            raise ValidationFailedError(
                "Elige un documento de tipo «Estudio socioeconómico» cargado en esta vacante."
            )
        try:
            text, ocr = self._documents.read_text(assessment.vacancy_id, file_id)
        except DocumentError as error:
            raise ValidationFailedError(str(error)) from error
        answer = self._ask(
            actor,
            assessment.vacancy_id,
            assistant.DOCUMENT_READING,
            assistant.DIGITIZATION_SYSTEM,
            assistant.digitization_request(version, text, ocr),
        )
        outcome = self._outcome(
            answer, lambda text: assistant.digitization_from_answer(version, text)
        )
        self._audit.record(
            AuditAction.ESTUDIO_DIGITALIZADO,
            result=AuditResult.PERMITIDO if outcome.content else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type="evaluacion",
            resource_id=assessment.id,
            ip=ip,
            details={"vacante": str(assessment.vacancy_id), "documento": str(file_id)},
        )
        return outcome

    def describe_photo(
        self,
        actor: Actor,
        assessment_id: uuid.UUID,
        file_id: uuid.UUID,
        *,
        field_id: str | None = None,
        ip: str | None = None,
    ) -> AiOutcome:
        """Pide a la IA que describa lo que se ve en una fotografía del estudio.

        Es una propuesta: no guarda nada. La persona la revisa, la corrige y la
        guarda con el estudio. La fotografía se envía reducida y sin metadatos."""
        assessment = self._load(actor, assessment_id, write=True)
        if assessment.kind is not Kind.ESTUDIO_SOCIOECONOMICO:
            raise ValidationFailedError(
                "Solo se describen fotografías de estudios socioeconómicos."
            )
        if not self._documents.belongs(assessment.vacancy_id, file_id, assessment.kind):
            raise ValidationFailedError(
                "Elige una fotografía de tipo «Estudio socioeconómico» cargada en esta vacante."
            )
        version = self._repo.template_version(assessment.template_version_id)  # type: ignore[arg-type]
        label = next(
            (item.label for item in (version.fields if version else ()) if item.id == field_id), ""
        )
        try:
            photo = self._documents.read_photo(assessment.vacancy_id, file_id)
        except DocumentError as error:
            raise ValidationFailedError(str(error)) from error
        answer = self._ask(
            actor,
            assessment.vacancy_id,
            assistant.PHOTO_DESCRIPTION,
            assistant.PHOTO_SYSTEM,
            assistant.photo_request(label),
            photos=(photo,),
        )
        outcome = self._outcome(answer, assistant.photo_from_answer)
        self._audit.record(
            AuditAction.ESTUDIO_FOTOGRAFIA_DESCRITA,
            result=AuditResult.PERMITIDO if outcome.content else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type="evaluacion",
            resource_id=assessment.id,
            ip=ip,
            details={"vacante": str(assessment.vacancy_id), "documento": str(file_id)},
        )
        return outcome

    # --- Síntesis del expediente ---------------------------------------------------------

    def syntheses(self, actor: Actor, application_id: uuid.UUID) -> SynthesisView:
        application = self._application(application_id)
        readable = self._access.readable(actor, application.vacancy_id)
        found = self._repo.syntheses(application_id)
        visible = [
            item
            for item in found
            if (not item.includes_psychometrics or Kind.PSICOMETRIA in readable)
            and (not item.includes_study or Kind.ESTUDIO_SOCIOECONOMICO in readable)
        ]
        return SynthesisView(
            latest=visible[0] if visible else None,
            total=len(visible),
            hidden=len(visible) < len(found),
        )

    def synthesize(
        self, actor: Actor, application_id: uuid.UUID, *, ip: str | None = None
    ) -> AiOutcome:
        """Pide a la IA una síntesis del expediente, separada por tipo de fuente.

        Entra: CV, evaluación inicial, llamadas, pruebas técnicas, entrevistas y
        psicometría solo si está validada por un profesional y quien la pide
        tiene ese permiso. Del estudio socioeconómico entran únicamente las
        descripciones guardadas junto a sus fotografías, y solo si quien la pide
        tiene el permiso del estudio; el resto del estudio (economía, salud,
        dictamen, niveles) nunca entra. No produce puntuaciones ni recomendaciones."""
        application = self._application(application_id)
        readable = self._access.readable(actor, application.vacancy_id)
        self._access.require(actor, application.vacancy_id, Kind.ENTREVISTA, write=True)
        material = self._applications.material(application_id)
        assessments = self._repo.for_application(application_id)
        usable = [
            item
            for item in assessments
            if (item.kind is Kind.PRUEBA_TECNICA and item.status in ("REALIZADA", "INCOMPLETA"))
            or (item.kind is Kind.ENTREVISTA and item.status == "REALIZADA")
            or (
                item.kind is Kind.PSICOMETRIA
                and item.status == "VALIDADA"
                and Kind.PSICOMETRIA in readable
            )
        ]
        pending = [
            f"{label} en estado {item.status}"
            for item in assessments
            for label in [_PENDING_LABELS.get((item.kind, item.status))]
            if label
        ]
        photos: list[PhotoNote] = []
        if Kind.ESTUDIO_SOCIOECONOMICO in readable:
            for item in assessments:
                if item.kind is Kind.ESTUDIO_SOCIOECONOMICO and item.status != "ANULADO":
                    version = self._repo.template_version(item.template_version_id)  # type: ignore[arg-type]
                    if version is not None:
                        photos += rules.photo_notes(version, item.data.get("answers") or {})
        sources = []
        if material.cv or material.evaluation:
            sources.append("CV")
        if material.calls:
            sources.append(f"{len(material.calls)} llamadas")
        for kind, label in (
            (Kind.PRUEBA_TECNICA, "pruebas técnicas"),
            (Kind.ENTREVISTA, "entrevistas"),
            (Kind.PSICOMETRIA, "pruebas psicométricas validadas"),
        ):
            count = sum(1 for item in usable if item.kind is kind)
            if count:
                sources.append(f"{count} {label}")
        if photos:
            sources.append(f"{len(photos)} fotografías del estudio")
        if not sources:
            raise ValidationFailedError(
                "El expediente todavía no tiene información que sintetizar."
            )
        answer = self._ask(
            actor,
            application.vacancy_id,
            assistant.DOSSIER_SYNTHESIS,
            assistant.SYNTHESIS_SYSTEM,
            assistant.synthesis_request(material, usable, pending, photos),
        )
        outcome = self._outcome(answer, assistant.synthesis_from_answer)
        if outcome.content is not None:
            synthesis = Synthesis(
                id=new_sequential_uuid(),
                application_id=application.id,
                vacancy_id=application.vacancy_id,
                created_at=self._clock(),
                created_by=actor.id,
                result=outcome.content,
                includes_psychometrics=any(item.kind is Kind.PSICOMETRIA for item in usable),
                includes_study=bool(photos),
                sources=tuple(sources),
            )
            self._repo.add_synthesis(synthesis)
            outcome = AiOutcome(synthesis)
        self._audit.record(
            AuditAction.EXPEDIENTE_SINTETIZADO,
            result=AuditResult.PERMITIDO if outcome.content else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type="postulacion",
            resource_id=application.id,
            ip=ip,
            details={"vacante": str(application.vacancy_id), "fuentes": sources},
        )
        return outcome


_PENDING_LABELS = {
    (Kind.PSICOMETRIA, "PENDIENTE"): "Prueba psicométrica",
    (Kind.PSICOMETRIA, "PRESENTADA"): "Prueba psicométrica sin validar por un profesional,",
    (Kind.PSICOMETRIA, "INCOMPLETA"): "Prueba psicométrica",
    (Kind.ENTREVISTA, "PROGRAMADA"): "Entrevista con gerente",
    (Kind.PRUEBA_TECNICA, "PENDIENTE"): "Prueba técnica",
    (Kind.ESTUDIO_SOCIOECONOMICO, "PENDIENTE"): "Estudio socioeconómico",
    (Kind.ESTUDIO_SOCIOECONOMICO, "EN_PROCESO"): "Estudio socioeconómico",
}

__all__ = ["SENSITIVE_KINDS", "AssessmentService"]
