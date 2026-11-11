"""Conecta el perfil y el prompt con la IA y con los documentos de la vacante."""

from __future__ import annotations

import uuid

from app.infrastructure.documents.text import TextExtractionError, extract_text
from app.infrastructure.storage.local import LocalFileStorage, StorageError
from app.modules.ai_settings.application.service import AiSettingsService
from app.modules.ai_settings.domain.models import Operation
from app.modules.evaluation_setup.domain.ports import AssistantAnswer, ProfileSourceError
from app.modules.file_management.domain.models import (
    DocumentType,
    FileAsset,
    FileRepository,
    FileStatus,
)

_UNREADABLE = {
    "sin_texto": "El documento no contiene texto legible; parece escaneado. Pega el texto "
    "del perfil en su lugar.",
    "formato_sin_texto": "Este formato todavía no se puede leer (DOC antiguo o imagen). Usa "
    "un PDF con texto o un DOCX, o pega el texto del perfil.",
    "protegido": "El PDF está protegido con contraseña.",
    "ilegible": "El documento está dañado o no se pudo leer.",
}


class AiAssistant:
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
        carries_document: bool,
    ) -> AssistantAnswer:
        result = self._ai.execute(
            Operation(operation),
            system=system,
            user=user,
            actor_user_id=actor_user_id,
            vacancy_id=vacancy_id,
            carries_document=carries_document,
        )
        return AssistantAnswer(
            ok=result.ok, text=result.text, complete=result.complete, error=result.error
        )


class StoredProfileSources:
    def __init__(self, files: FileRepository, storage: LocalFileStorage | None) -> None:
        self._files = files
        self._storage = storage

    def _asset(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> FileAsset | None:
        asset = self._files.get(file_id)
        if (
            asset is None
            or asset.vacancy_id != vacancy_id
            or asset.status is not FileStatus.CONFIRMADO
            or asset.document_type is not DocumentType.PERFIL_PUESTO
        ):
            return None
        return asset

    def is_profile_document(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> bool:
        return self._asset(vacancy_id, file_id) is not None

    def read_text(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> tuple[str, bool]:
        asset = self._asset(vacancy_id, file_id)
        if asset is None or self._storage is None:
            raise ProfileSourceError(
                "Elige un documento de tipo «Perfil de puesto» cargado en esta vacante."
            )
        try:
            with self._storage.open(asset.storage_key) as handle:
                return extract_text(handle, asset.extension)
        except TextExtractionError as error:
            raise ProfileSourceError(_UNREADABLE[error.code]) from error
        except (StorageError, OSError) as error:
            raise ProfileSourceError(
                "El documento no está disponible en el almacenamiento."
            ) from error
