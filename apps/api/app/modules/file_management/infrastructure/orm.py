"""Tabla de documentos almacenados (esquema ``files``)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    GUID,
    SCHEMA_AUTH,
    SCHEMA_FILES,
    SCHEMA_VACANCY,
    Base,
    UTCDateTime,
)

_USER_FK = f"{SCHEMA_AUTH}.users.id"


class FileAssetRow(Base):
    __tablename__ = "file_assets"
    __table_args__ = (
        sa.Index("ix_file_assets_vacancy", "vacancy_id", "status"),
        sa.Index("ix_file_assets_hash", "vacancy_id", "sha256"),
        sa.Index("ix_file_assets_status", "status", "created_at"),
        {"schema": SCHEMA_FILES},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_VACANCY}.vacancies.id")
    )
    document_type: Mapped[str] = mapped_column(sa.String(40))
    sensitive_class: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    original_name: Mapped[str] = mapped_column(sa.Unicode(200))
    extension: Mapped[str] = mapped_column(sa.String(10))
    content_type: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    stored_size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    stored_sha256: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    encryption_key_id: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    storage_backend: Mapped[str] = mapped_column(sa.String(20))
    # Referencia lógica relativa; la ruta absoluta solo existe en la configuración.
    storage_key: Mapped[str] = mapped_column(sa.String(200), unique=True)
    status: Mapped[str] = mapped_column(sa.String(20))
    malware_scan: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    retention_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    deletion_reason: Mapped[str | None] = mapped_column(sa.Unicode(500), nullable=True)
