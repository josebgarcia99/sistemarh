"""Conecta las evaluaciones posteriores con permisos, documentos, expediente e IA."""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from typing import Any

from app.composition.file_access import VacancyFileAccessPolicy, is_study_analyst
from app.core.security.master_key import DecryptionError, MasterKey
from app.infrastructure.documents.photos import (
    PHOTO_EXTENSIONS,
    PhotoError,
    pdf_pages,
    prepare_photo,
)
from app.infrastructure.documents.text import Ocr, TextExtractionError, extract_text
from app.infrastructure.documents.xlsx_template import TemplateError
from app.infrastructure.storage.local import LocalFileStorage, StorageError, build_key
from app.modules.ai_settings.application.service import AiSettingsService
from app.modules.ai_settings.domain.models import ImageInput, Operation
from app.modules.assessments.domain.models import (
    SENSITIVE_KINDS,
    Actor,
    ApplicationRef,
    AssistantAnswer,
    Closure,
    DocumentError,
    DossierMaterial,
    FormTemplateVersion,
    Kind,
    Photo,
    StudyFile,
)
from app.modules.assessments.infrastructure.study_workbook import check_format, fill_study
from app.modules.cv_processing.domain.models import CvBatchRepository
from app.modules.evaluation_setup.domain.models import EvaluationSetupRepository
from app.modules.file_management.domain.models import DocumentType, FileRepository, FileStatus
from app.modules.phone_calls.domain.models import PhoneCallRepository
from app.modules.recruitment.domain.models import (
    ApplicationStatus,
    OutcomeKind,
    RecruitmentRepository,
)
from app.modules.vacancies.domain.models import VacancyRepository

_DOCUMENT_TYPES = {
    Kind.PSICOMETRIA: DocumentType.PSICOMETRIA,
    Kind.PRUEBA_TECNICA: DocumentType.PRUEBA_TECNICA,
    Kind.ESTUDIO_SOCIOECONOMICO: DocumentType.ESTUDIO_SOCIOECONOMICO,
    Kind.ENTREVISTA: DocumentType.ADJUNTO,
    Kind.REFERENCIAS: DocumentType.ADJUNTO,
}
_OUTCOME_LABELS = {
    OutcomeKind.NO_CONTRATADO: "No contratado",
    OutcomeKind.DESISTIO: "Desistió",
    OutcomeKind.NO_LOCALIZADO: "No localizado",
    OutcomeKind.VACANTE_CANCELADA: "Vacante cancelada",
    OutcomeKind.OTRO_CIERRE: "Otro cierre",
}
_UNREADABLE = {
    "sin_texto": "No se encontró texto legible en el documento.",
    "formato_sin_texto": "Este formato todavía no se puede leer (DOC antiguo, o imagen sin el "
    "lector de documentos escaneados instalado).",
    "protegido": "El PDF está protegido con contraseña.",
    "ilegible": "El documento está dañado o no se pudo leer.",
    "ocr_fallido": "El lector de documentos escaneados no pudo procesar el archivo.",
}


class VacancyAssessmentAccess:
    """La psicometría y el estudio socioeconómico usan el mismo permiso
    adicional que sus documentos."""

    def __init__(self, vacancies: VacancyRepository) -> None:
        self._policy = VacancyFileAccessPolicy(vacancies)

    def require(self, actor: Actor, vacancy_id: uuid.UUID, kind: Kind, *, write: bool) -> None:
        if kind is Kind.REFERENCIAS and is_study_analyst(actor):
            # Las referencias las trabajan RH y el analista de estudios. Al
            # analista le basta su puesto; solo se comprueba que la vacante exista.
            self._policy.readable_sensitive_classes(actor, vacancy_id)
            return
        sensitive = kind.value if kind in SENSITIVE_KINDS else None
        check = self._policy.require_write if write else self._policy.require_read
        check(actor, vacancy_id, sensitive)

    def readable(self, actor: Actor, vacancy_id: uuid.UUID) -> frozenset[Kind]:
        granted = self._policy.readable_sensitive_classes(actor, vacancy_id)
        if is_study_analyst(actor):
            # Ni entrevistas ni pruebas técnicas: solo el estudio y las referencias.
            return frozenset({Kind.ESTUDIO_SOCIOECONOMICO, Kind.REFERENCIAS})
        return frozenset(k for k in Kind if k not in SENSITIVE_KINDS or k.value in granted)


class AssessmentApplications:
    def __init__(
        self,
        recruitment: RecruitmentRepository,
        batches: CvBatchRepository,
        calls: PhoneCallRepository,
        setup: EvaluationSetupRepository,
    ) -> None:
        self._recruitment = recruitment
        self._batches = batches
        self._calls = calls
        self._setup = setup

    def get(self, application_id: uuid.UUID) -> ApplicationRef | None:
        application = self._recruitment.application(application_id)
        if application is None:
            return None
        return ApplicationRef(
            id=application.id,
            vacancy_id=application.vacancy_id,
            active=application.status is ApplicationStatus.ACTIVA,
        )

    def material(self, application_id: uuid.UUID) -> DossierMaterial:
        application = self._recruitment.application(application_id)
        if application is None:
            return DossierMaterial()
        item = (
            self._batches.get_item(application.evaluation_item_id)
            if application.evaluation_item_id
            else None
        )
        profiles = self._setup.profile_versions(application.vacancy_id)
        requirements = (
            (*profiles[0].content.must_have, *profiles[0].content.nice_to_have) if profiles else ()
        )
        calls = []
        for call in reversed(self._calls.calls(application_id)):
            answers = {answer.question_id: answer for answer in call.answers}
            rows = [
                {
                    "pregunta": question.text,
                    "respuesta": answers[question.id].answer,
                    "observacion": answers[question.id].notes,
                }
                for question in call.active_questions
                if question.id in answers and answers[question.id].answer
            ]
            if rows or call.notes:
                calls.append(
                    {
                        "fecha": call.called_at.date().isoformat(),
                        "preguntas": rows,
                        "observaciones": call.notes,
                        "atencion": (call.analysis or {}).get("puntos_de_atencion") or [],
                    }
                )
        names: dict[str, str] = {}
        batch = self._batches.get_batch(item.batch_id) if item else None
        version = self._setup.prompt_version(batch.prompt_version_id) if batch else None
        if version is not None:
            names = {criterion.code: criterion.name for criterion in version.criteria}
        return DossierMaterial(
            requirements=requirements,
            cv=(item.extraction if item else None) or {},
            evaluation=(item.result if item else None) or {},
            calls=tuple(calls),
            cv_classification=application.ai_classification or "",
            cv_score=str(application.ai_score) if application.ai_score is not None else "",
            criteria_names=names,
        )

    def closure(self, application_id: uuid.UUID) -> Closure | None:
        application = self._recruitment.application(application_id)
        if application is None or application.status is ApplicationStatus.ACTIVA:
            return None
        outcome = self._recruitment.current_outcome(application.id)
        if outcome is None or outcome.outcome is OutcomeKind.CONTRATADO:
            return None
        campaign = self._recruitment.campaign(application.campaign_id)
        pipeline = self._recruitment.pipeline(campaign.pipeline_version_id) if campaign else None
        stage = next(
            (s.name for s in (pipeline.stages if pipeline else ()) if s.id == application.stage_id),
            "Sin datos",
        )
        return Closure(
            stage=stage,
            outcome=_OUTCOME_LABELS.get(outcome.outcome, outcome.outcome.value),
            reason=outcome.reason or "Sin motivo escrito",
        )


class AssessmentDocuments:
    def __init__(
        self,
        files: FileRepository,
        storage: LocalFileStorage | None,
        cipher: MasterKey | None,
        ocr: Ocr | None,
    ) -> None:
        self._files = files
        self._storage = storage
        self._cipher = cipher
        self._ocr = ocr

    def _asset(self, vacancy_id: uuid.UUID, file_id: uuid.UUID):  # noqa: ANN202
        asset = self._files.get(file_id)
        if (
            asset is None
            or asset.vacancy_id != vacancy_id
            or asset.status is not FileStatus.CONFIRMADO
        ):
            return None
        return asset

    def belongs(self, vacancy_id: uuid.UUID, file_id: uuid.UUID, kind: Kind) -> bool:
        asset = self._asset(vacancy_id, file_id)
        return asset is not None and asset.document_type is _DOCUMENT_TYPES[kind]

    def _content(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> tuple[str, bytes]:
        """Extensión y contenido original del documento, ya descifrado."""
        asset = self._asset(vacancy_id, file_id)
        if asset is None or self._storage is None:
            raise DocumentError("El documento no está disponible.")
        try:
            chunks = self._storage.read_chunks(asset.storage_key)
            if asset.encryption_key_id is not None:
                # Los documentos sensibles están cifrados en el disco.
                if self._cipher is None or self._cipher.key_id != asset.encryption_key_id:
                    raise DocumentError(
                        "El documento está cifrado con una clave que no está disponible."
                    )
                chunks = self._cipher.decrypt_chunks(chunks)
            return asset.extension, b"".join(chunks)
        except (StorageError, OSError, DecryptionError) as error:
            raise DocumentError("El documento no se pudo leer del almacenamiento.") from error

    def read_text(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> tuple[str, bool]:
        extension, content = self._content(vacancy_id, file_id)
        try:
            found = extract_text(io.BytesIO(content), extension, self._ocr)
        except TextExtractionError as error:
            raise DocumentError(_UNREADABLE[error.code]) from error
        return found.text, found.ocr

    def read_pages(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> tuple[Photo, ...]:
        try:
            extension, content = self._content(vacancy_id, file_id)
            if extension == "pdf":
                return tuple(Photo("image/jpeg", page) for page in pdf_pages(content))
            if extension in PHOTO_EXTENSIONS:
                return (Photo("image/jpeg", prepare_photo(content)),)
        except (DocumentError, PhotoError):
            # Sin imágenes se sigue con el texto: no es motivo para detener el resumen.
            pass
        return ()

    def read_photo(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> Photo:
        extension, content = self._content(vacancy_id, file_id)
        if extension not in PHOTO_EXTENSIONS:
            raise DocumentError("Para describirla, la fotografía debe ser una imagen JPG o PNG.")
        try:
            return Photo("image/jpeg", prepare_photo(content))
        except PhotoError as error:
            raise DocumentError("La imagen está dañada o no se pudo leer.") from error


class StoredStudyFormats:
    """El Excel en blanco del estudio que cargó un administrador. Se guarda en el
    almacenamiento de documentos del servidor, uno por formulario, fuera de las
    vacantes; no contiene datos de ninguna persona."""

    AREA, FOLDER = "private", "formato_estudio"

    def __init__(self, storage: LocalFileStorage | None) -> None:
        self._storage = storage

    def key(self, template_id: uuid.UUID) -> str:
        return build_key(self.AREA, self.FOLDER, template_id)

    def exists(self, template_id: uuid.UUID) -> bool:
        return self._storage is not None and self._storage.exists(self.key(template_id))

    def save(self, template_id: uuid.UUID, content: bytes) -> list[str]:
        if self._storage is None:
            raise DocumentError("El almacenamiento de documentos no está disponible.")
        try:
            missing = check_format(content)
        except TemplateError as error:
            raise DocumentError(str(error)) from error
        temporary = uuid.uuid4()
        key = self.key(template_id)
        try:
            with self._storage.open_temp(temporary) as handle:
                handle.write(content)
            # Sustituye al anterior: el formato vigente es siempre el último cargado.
            self._storage.delete(key)
            self._storage.commit(temporary, key)
        except (OSError, StorageError) as error:
            self._storage.discard_temp(temporary)
            raise DocumentError("No se pudo guardar el formato en el almacenamiento.") from error
        return missing

    def fill(
        self,
        template_id: uuid.UUID,
        version: FormTemplateVersion,
        data: dict[str, Any],
        photo: Callable[[str], bytes | None],
    ) -> StudyFile | None:
        if not self.exists(template_id):
            return None
        assert self._storage is not None
        template = b"".join(self._storage.read_chunks(self.key(template_id)))
        try:
            filled = fill_study(template, version, data, photo)
        except TemplateError as error:
            raise DocumentError(str(error)) from error
        return StudyFile(filled.content, tuple(filled.unplaced))


class AssessmentAssistant:
    def __init__(self, ai: AiSettingsService) -> None:
        self._ai = ai

    def ask(
        self,
        operation: str,
        *,
        system: str,
        user: str,
        vacancy_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        photos: tuple[Photo, ...] = (),
    ) -> AssistantAnswer:
        result = self._ai.execute(
            Operation(operation),
            system=system,
            user=user,
            actor_user_id=actor_user_id,
            vacancy_id=vacancy_id,
            # Siempre lleva datos de una persona candidata.
            carries_document=True,
            images=tuple(ImageInput(photo.media_type, photo.data) for photo in photos),
        )
        return AssistantAnswer(
            ok=result.ok, text=result.text, complete=result.complete, error=result.error
        )
