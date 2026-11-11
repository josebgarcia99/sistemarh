from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.file_management.application.reconciliation import ReconciliationReport
from app.modules.file_management.domain.models import DocumentType, FileAsset


class FileOut(BaseModel):
    """Metadatos de un documento. Nunca incluye su ubicación física."""

    id: uuid.UUID
    vacancy_id: uuid.UUID
    document_type: DocumentType
    sensitive: bool
    original_name: str
    content_type: str | None
    size_bytes: int | None
    sha256: str | None
    malware_scan: str | None
    uploaded_by: uuid.UUID
    uploaded_by_name: str | None
    created_at: datetime

    @classmethod
    def of(cls, asset: FileAsset, names: dict[uuid.UUID, str]) -> FileOut:
        return cls(
            id=asset.id,
            vacancy_id=asset.vacancy_id,
            document_type=asset.document_type,
            sensitive=asset.sensitive_class is not None,
            original_name=asset.original_name,
            content_type=asset.content_type,
            size_bytes=asset.size_bytes,
            sha256=asset.sha256,
            malware_scan=asset.malware_scan.value if asset.malware_scan else None,
            uploaded_by=asset.uploaded_by,
            uploaded_by_name=names.get(asset.uploaded_by),
            created_at=asset.created_at,
        )


class FileUploadOut(BaseModel):
    file: FileOut
    # Documentos de la misma vacante con el mismo contenido.
    duplicates: list[FileOut]


class FileDeletionIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class StorageStatusOut(BaseModel):
    free_bytes: int
    max_upload_bytes: int
    antivirus: str
    files_by_status: dict[str, int]


class ReconciliationIn(BaseModel):
    # none: sin recalcular hashes; sample: los 200 más antiguos; all: todos.
    verify_hashes: Literal["none", "sample", "all"] = "sample"


class ReconciliationOut(BaseModel):
    consistent: bool
    stale_uploads_failed: int
    temp_files_removed: int
    orphans_quarantined: int
    missing_files: list[uuid.UUID]
    size_mismatches: list[uuid.UUID]
    hash_mismatches: list[uuid.UUID]
    deleted_files_removed: int
    confirmed_checked: int
    hashes_verified: int

    @classmethod
    def of(cls, report: ReconciliationReport) -> ReconciliationOut:
        return cls(
            consistent=report.consistent,
            stale_uploads_failed=report.stale_uploads_failed,
            temp_files_removed=report.temp_files_removed,
            orphans_quarantined=len(report.orphans_quarantined),
            missing_files=report.missing_files,
            size_mismatches=report.size_mismatches,
            hash_mismatches=report.hash_mismatches,
            deleted_files_removed=report.deleted_files_removed,
            confirmed_checked=report.confirmed_checked,
            hashes_verified=report.hashes_verified,
        )
