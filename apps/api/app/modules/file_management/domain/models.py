"""Documentos almacenados: metadatos, estados y puertos.

Este módulo no conoce las reglas de reclutamiento. Quién puede leer o
escribir los documentos de una vacante lo decide ``FileAccessPolicy``, que
otro componente implementa.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class DocumentType(StrEnum):
    CV = "CV"
    PERFIL_PUESTO = "PERFIL_PUESTO"
    PSICOMETRIA = "PSICOMETRIA"
    PRUEBA_TECNICA = "PRUEBA_TECNICA"
    ESTUDIO_SOCIOECONOMICO = "ESTUDIO_SOCIOECONOMICO"
    ADJUNTO = "ADJUNTO"
    # Generados por el sistema; nadie los carga.
    REPORTE_EVALUACION = "REPORTE_EVALUACION"
    PAQUETE_CV = "PAQUETE_CV"


# Carpeta física de cada tipo. Ningún nombre de persona aparece en el disco.
STORAGE_FOLDERS: dict[DocumentType, str] = {
    DocumentType.CV: "cv",
    DocumentType.PERFIL_PUESTO: "job_profiles",
    DocumentType.PSICOMETRIA: "psychometrics",
    DocumentType.PRUEBA_TECNICA: "technical_tests",
    DocumentType.ESTUDIO_SOCIOECONOMICO: "socioeconomic_studies",
    DocumentType.ADJUNTO: "attachments",
    DocumentType.REPORTE_EVALUACION: "evaluation_reports",
    DocumentType.PAQUETE_CV: "cv_packages",
}

# Exportaciones que produce el sistema. Viven en el área ``generated``.
GENERATED_TYPES = frozenset({DocumentType.REPORTE_EVALUACION, DocumentType.PAQUETE_CV})
GENERATED_CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
}

# Tipos que admiten además una hoja de cálculo: los que tienen un formato de la
# empresa en Excel.
SPREADSHEET_TYPES = frozenset({DocumentType.PERFIL_PUESTO, DocumentType.ESTUDIO_SOCIOECONOMICO})

# Tipos que exigen un permiso adicional por persona, además del acceso a la vacante.
SENSITIVE_CLASSES: dict[DocumentType, str] = {
    DocumentType.PSICOMETRIA: "PSICOMETRIA",
    DocumentType.ESTUDIO_SOCIOECONOMICO: "ESTUDIO_SOCIOECONOMICO",
}


class FileStatus(StrEnum):
    """Estados explícitos: el disco y SQL Server no comparten transacción."""

    RECIBIENDO = "RECIBIENDO"  # registro creado; el archivo aún no está confirmado
    CONFIRMADO = "CONFIRMADO"  # archivo en su ubicación definitiva y verificado
    RECHAZADO = "RECHAZADO"  # no pasó la validación; no se guardó
    FALLIDO = "FALLIDO"  # la escritura se interrumpió; no se guardó
    ELIMINADO = "ELIMINADO"  # eliminación autorizada; se conservan los metadatos


class MalwareScan(StrEnum):
    LIMPIO = "LIMPIO"
    NO_ANALIZADO = "NO_ANALIZADO"


@dataclass
class FileAsset:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    document_type: DocumentType
    sensitive_class: str | None
    original_name: str
    extension: str
    storage_backend: str
    storage_key: str
    status: FileStatus
    uploaded_by: uuid.UUID
    created_at: datetime
    content_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    # Lo que hay en el disco. Coincide con el contenido salvo en archivos cifrados.
    stored_size_bytes: int | None = None
    stored_sha256: str | None = None
    # Identificador de la clave maestra con que se cifró; vacío si no está cifrado.
    encryption_key_id: str | None = None
    malware_scan: MalwareScan | None = None
    failure_code: str | None = None
    confirmed_at: datetime | None = None
    retention_until: datetime | None = None
    deleted_at: datetime | None = None
    deleted_by: uuid.UUID | None = None
    deletion_reason: str | None = None


class Actor(Protocol):
    """Lo que este módulo necesita saber de quien hace la operación."""

    id: uuid.UUID

    @property
    def is_admin(self) -> bool: ...


class FileAccessPolicy(Protocol):
    """Decide el acceso a los documentos de una vacante, en el momento de usarlos."""

    def require_read(
        self, actor: Actor, vacancy_id: uuid.UUID, sensitive_class: str | None
    ) -> None: ...

    def require_write(
        self, actor: Actor, vacancy_id: uuid.UUID, sensitive_class: str | None
    ) -> None: ...

    def readable_sensitive_classes(self, actor: Actor, vacancy_id: uuid.UUID) -> frozenset[str]:
        """Clases sensibles que el usuario puede ver en esa vacante."""
        ...


class FileRepository(Protocol):
    def add(self, asset: FileAsset) -> None: ...

    def save(self, asset: FileAsset) -> None: ...

    def get(self, file_id: uuid.UUID) -> FileAsset | None: ...

    def list_for_vacancy(self, vacancy_id: uuid.UUID, status: FileStatus) -> list[FileAsset]: ...

    def find_by_hash(
        self, vacancy_id: uuid.UUID, sha256: str, *, exclude_id: uuid.UUID
    ) -> list[FileAsset]:
        """Documentos confirmados de la vacante con el mismo contenido."""
        ...

    def list_by_status(self, status: FileStatus) -> list[FileAsset]: ...

    def count_by_status(self) -> dict[FileStatus, int]: ...
