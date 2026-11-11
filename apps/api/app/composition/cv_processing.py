"""Conecta la evaluación de CV con documentos, prompts aprobados e IA."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from typing import BinaryIO

from app.infrastructure.documents.text import TextExtractionError, extract_text
from app.infrastructure.storage.local import LocalFileStorage, StorageError
from app.modules.ai_settings.application.service import AiSettingsService
from app.modules.ai_settings.domain.models import Operation
from app.modules.cv_processing.domain.ports import (
    AiAnswer,
    CvFile,
    Rubric,
    RubricCriterion,
    UnreadableCvError,
)
from app.modules.evaluation_setup.domain.generator import render_prompt
from app.modules.evaluation_setup.domain.models import (
    EvaluationSetupRepository,
    PromptStatus,
    PromptVersion,
)
from app.modules.file_management.application.service import FileService
from app.modules.file_management.domain.models import (
    DocumentType,
    FileAsset,
    FileRepository,
    FileStatus,
)

_EXPORT_TYPES = {
    "reporte": DocumentType.REPORTE_EVALUACION,
    "paquete": DocumentType.PAQUETE_CV,
}
# Espacio para niveles, evidencias y justificaciones de toda la rúbrica.
_MAX_OUTPUT_TOKENS = 6000


def _cv(asset: FileAsset) -> CvFile:
    return CvFile(
        id=asset.id,
        name=asset.original_name,
        extension=asset.extension,
        sha256=asset.sha256 or "",
        size_bytes=asset.size_bytes or 0,
    )


class StoredCvFiles:
    def __init__(
        self, files: FileRepository, storage: LocalFileStorage, service: FileService
    ) -> None:
        self._files = files
        self._storage = storage
        self._service = service

    def confirmed_cvs(self, vacancy_id: uuid.UUID) -> list[CvFile]:
        return [
            _cv(asset)
            for asset in self._files.list_for_vacancy(vacancy_id, FileStatus.CONFIRMADO)
            if asset.document_type is DocumentType.CV
        ]

    def _asset(self, file_id: uuid.UUID) -> FileAsset | None:
        asset = self._files.get(file_id)
        if (
            asset is None
            or asset.status is not FileStatus.CONFIRMADO
            or asset.document_type is not DocumentType.CV
        ):
            return None
        return asset

    def get(self, file_id: uuid.UUID) -> CvFile | None:
        asset = self._asset(file_id)
        return _cv(asset) if asset is not None else None

    def read_text(self, file_id: uuid.UUID) -> tuple[str, bool]:
        asset = self._asset(file_id)
        if asset is None:
            raise UnreadableCvError("archivo_no_disponible")
        try:
            with self._storage.open(asset.storage_key) as handle:
                return extract_text(handle, asset.extension)
        except TextExtractionError as error:
            raise UnreadableCvError(error.code) from error
        except (StorageError, OSError) as error:
            raise UnreadableCvError("archivo_no_disponible") from error

    def read_chunks(self, file_id: uuid.UUID) -> Iterator[bytes]:
        asset = self._asset(file_id)
        if asset is None:
            raise StorageError("El CV ya no está disponible.")
        return self._storage.read_chunks(asset.storage_key)

    def store_export(
        self,
        *,
        vacancy_id: uuid.UUID,
        kind: str,
        name: str,
        write: Callable[[BinaryIO], None],
        created_by: uuid.UUID,
    ) -> uuid.UUID:
        return self._service.store_generated(
            vacancy_id=vacancy_id,
            document_type=_EXPORT_TYPES[kind],
            name=name,
            write=write,
            created_by=created_by,
        ).id


def _rubric(version: PromptVersion) -> Rubric:
    return Rubric(
        prompt_version_id=version.id,
        version_number=version.version_number,
        system_prompt=render_prompt(version),
        criteria=tuple(RubricCriterion(c.code, c.name, c.weight) for c in version.criteria),
        threshold=version.pass_threshold,
    )


class ApprovedRubrics:
    def __init__(self, repo: EvaluationSetupRepository) -> None:
        self._repo = repo

    def approved(self, vacancy_id: uuid.UUID) -> Rubric | None:
        for version in self._repo.prompt_versions(vacancy_id):
            if version.status is PromptStatus.APROBADO:
                return _rubric(version)
        return None

    def get(self, prompt_version_id: uuid.UUID) -> Rubric | None:
        # Un lote ya creado se termina con su versión aunque luego se archive.
        version = self._repo.prompt_version(prompt_version_id)
        return _rubric(version) if version is not None else None


class AiEvaluator:
    def __init__(self, ai: AiSettingsService) -> None:
        self._ai = ai

    def ensure_ready(self) -> None:
        self._ai.ensure_ready(Operation.EVALUACION_DOCUMENTAL, carries_document=True)

    def evaluate(
        self, *, system: str, user: str, vacancy_id: uuid.UUID, actor_user_id: uuid.UUID
    ) -> AiAnswer:
        result = self._ai.execute(
            Operation.EVALUACION_DOCUMENTAL,
            system=system,
            user=user,
            actor_user_id=actor_user_id,
            vacancy_id=vacancy_id,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            carries_document=True,
        )
        return AiAnswer(
            ok=result.ok,
            text=result.text,
            complete=result.complete,
            error=result.error,
            execution_id=result.execution_id,
        )
