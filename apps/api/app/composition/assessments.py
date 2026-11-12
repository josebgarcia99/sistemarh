"""Conecta las evaluaciones posteriores con permisos, documentos, expediente e IA."""

from __future__ import annotations

import io
import uuid

from app.composition.file_access import VacancyFileAccessPolicy, is_study_analyst
from app.core.security.master_key import DecryptionError, MasterKey
from app.infrastructure.documents.photos import PHOTO_EXTENSIONS, PhotoError, prepare_photo
from app.infrastructure.documents.text import Ocr, TextExtractionError, extract_text
from app.infrastructure.storage.local import LocalFileStorage, StorageError
from app.modules.ai_settings.application.service import AiSettingsService
from app.modules.ai_settings.domain.models import ImageInput, Operation
from app.modules.assessments.domain.models import (
    SENSITIVE_KINDS,
    Actor,
    ApplicationRef,
    AssistantAnswer,
    DocumentError,
    DossierMaterial,
    Kind,
    Photo,
)
from app.modules.cv_processing.domain.models import CvBatchRepository
from app.modules.evaluation_setup.domain.models import EvaluationSetupRepository
from app.modules.file_management.domain.models import DocumentType, FileRepository, FileStatus
from app.modules.phone_calls.domain.models import PhoneCallRepository
from app.modules.recruitment.domain.models import ApplicationStatus, RecruitmentRepository
from app.modules.vacancies.domain.models import VacancyRepository

_DOCUMENT_TYPES = {
    Kind.PSICOMETRIA: DocumentType.PSICOMETRIA,
    Kind.PRUEBA_TECNICA: DocumentType.PRUEBA_TECNICA,
    Kind.ESTUDIO_SOCIOECONOMICO: DocumentType.ESTUDIO_SOCIOECONOMICO,
    Kind.ENTREVISTA: DocumentType.ADJUNTO,
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
        sensitive = kind.value if kind in SENSITIVE_KINDS else None
        check = self._policy.require_write if write else self._policy.require_read
        check(actor, vacancy_id, sensitive)

    def readable(self, actor: Actor, vacancy_id: uuid.UUID) -> frozenset[Kind]:
        granted = self._policy.readable_sensitive_classes(actor, vacancy_id)
        if is_study_analyst(actor):
            # Ni entrevistas ni pruebas técnicas: solo el estudio.
            return frozenset({Kind.ESTUDIO_SOCIOECONOMICO})
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
            version = self._calls.version(call.bank_version_id)
            answers = {answer.question_id: answer for answer in call.answers}
            rows = [
                {
                    "pregunta": question.text,
                    "respuesta": answers[question.id].answer,
                    "observacion": answers[question.id].notes,
                }
                for question in (version.questions if version else ())
                if question.id in answers and answers[question.id].answer
            ]
            if rows or call.notes:
                calls.append(
                    {
                        "fecha": call.called_at.date().isoformat(),
                        "preguntas": rows,
                        "observaciones": call.notes,
                    }
                )
        return DossierMaterial(
            requirements=requirements,
            cv=(item.extraction if item else None) or {},
            evaluation=(item.result if item else None) or {},
            calls=tuple(calls),
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

    def read_photo(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> Photo:
        extension, content = self._content(vacancy_id, file_id)
        if extension not in PHOTO_EXTENSIONS:
            raise DocumentError("Para describirla, la fotografía debe ser una imagen JPG o PNG.")
        try:
            return Photo("image/jpeg", prepare_photo(content))
        except PhotoError as error:
            raise DocumentError("La imagen está dañada o no se pudo leer.") from error


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
