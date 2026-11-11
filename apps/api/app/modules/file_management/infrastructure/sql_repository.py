"""Repositorio de documentos sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import uuid
from dataclasses import fields

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.file_management.domain.models import (
    DocumentType,
    FileAsset,
    FileStatus,
    MalwareScan,
)
from app.modules.file_management.infrastructure.orm import FileAssetRow

_FIELDS = tuple(f.name for f in fields(FileAsset) if f.name != "id")


def _to_row_values(asset: FileAsset) -> dict[str, object]:
    values = {name: getattr(asset, name) for name in _FIELDS}
    values["document_type"] = asset.document_type.value
    values["status"] = asset.status.value
    values["malware_scan"] = asset.malware_scan.value if asset.malware_scan else None
    return values


def _to_asset(row: FileAssetRow) -> FileAsset:
    values = {name: getattr(row, name) for name in _FIELDS}
    values["document_type"] = DocumentType(row.document_type)
    values["status"] = FileStatus(row.status)
    values["malware_scan"] = MalwareScan(row.malware_scan) if row.malware_scan else None
    return FileAsset(id=row.id, **values)


class SqlFileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, asset: FileAsset) -> None:
        self._session.add(FileAssetRow(id=asset.id, **_to_row_values(asset)))
        self._session.flush()

    def save(self, asset: FileAsset) -> None:
        row = self._session.get(FileAssetRow, asset.id)
        if row is None:
            raise LookupError("El documento no existe.")
        for name, value in _to_row_values(asset).items():
            setattr(row, name, value)
        self._session.flush()

    def get(self, file_id: uuid.UUID) -> FileAsset | None:
        row = self._session.get(FileAssetRow, file_id)
        return _to_asset(row) if row is not None else None

    def _select(self, *conditions: sa.ColumnElement[bool]) -> list[FileAsset]:
        rows = self._session.execute(
            sa.select(FileAssetRow)
            .where(*conditions)
            .order_by(FileAssetRow.created_at, FileAssetRow.id)
        ).scalars()
        return [_to_asset(row) for row in rows]

    def list_for_vacancy(self, vacancy_id: uuid.UUID, status: FileStatus) -> list[FileAsset]:
        return self._select(
            FileAssetRow.vacancy_id == vacancy_id, FileAssetRow.status == status.value
        )

    def find_by_hash(
        self, vacancy_id: uuid.UUID, sha256: str, *, exclude_id: uuid.UUID
    ) -> list[FileAsset]:
        return self._select(
            FileAssetRow.vacancy_id == vacancy_id,
            FileAssetRow.sha256 == sha256,
            FileAssetRow.status == FileStatus.CONFIRMADO.value,
            FileAssetRow.id != exclude_id,
        )

    def list_by_status(self, status: FileStatus) -> list[FileAsset]:
        return self._select(FileAssetRow.status == status.value)

    def count_by_status(self) -> dict[FileStatus, int]:
        rows = self._session.execute(
            sa.select(FileAssetRow.status, sa.func.count()).group_by(FileAssetRow.status)
        ).all()
        return {FileStatus(status): count for status, count in rows}
