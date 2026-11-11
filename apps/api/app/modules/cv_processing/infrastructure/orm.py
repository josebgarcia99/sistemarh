"""Tablas de los lotes de evaluación de CV (esquema ``ai``)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    GUID,
    SCHEMA_AI,
    SCHEMA_AUTH,
    SCHEMA_FILES,
    SCHEMA_VACANCY,
    Base,
    UTCDateTime,
    long_text,
)

_FILE_FK = f"{SCHEMA_FILES}.file_assets.id"


class CvBatchRow(Base):
    __tablename__ = "cv_batches"
    __table_args__ = (
        sa.Index("ix_cv_batches_vacancy", "vacancy_id", "created_at"),
        sa.Index("ix_cv_batches_status", "status"),
        {"schema": SCHEMA_AI},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_VACANCY}.vacancies.id")
    )
    prompt_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_AI}.prompt_versions.id")
    )
    status: Mapped[str] = mapped_column(sa.String(30))
    total: Mapped[int] = mapped_column(sa.Integer)
    error: Mapped[str | None] = mapped_column(sa.Unicode(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{SCHEMA_AUTH}.users.id"))
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    report_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_FILE_FK), nullable=True
    )
    accepted_zip_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_FILE_FK), nullable=True
    )
    rejected_zip_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_FILE_FK), nullable=True
    )
    unevaluable_zip_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_FILE_FK), nullable=True
    )
    runner_token: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class CvBatchItemRow(Base):
    __tablename__ = "cv_batch_items"
    __table_args__ = (
        sa.UniqueConstraint("batch_id", "position", name="uq_cv_batch_items_position"),
        sa.UniqueConstraint("batch_id", "file_id", name="uq_cv_batch_items_file"),
        sa.Index("ix_cv_batch_items_status", "batch_id", "status"),
        sa.Index("ix_cv_batch_items_file", "file_id"),
        {"schema": SCHEMA_AI},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{SCHEMA_AI}.cv_batches.id"))
    file_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_FILE_FK))
    position: Mapped[int] = mapped_column(sa.Integer)
    status: Mapped[str] = mapped_column(sa.String(20))
    step: Mapped[str] = mapped_column(sa.String(20))
    attempts: Mapped[int] = mapped_column(sa.Integer)
    classification: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2), nullable=True)
    result: Mapped[str | None] = mapped_column(long_text(), nullable=True)
    extraction: Mapped[str | None] = mapped_column(long_text(), nullable=True)
    error_code: Mapped[str | None] = mapped_column(sa.String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Unicode(500), nullable=True)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_AI}.cv_batch_items.id"), nullable=True
    )
    # Sin clave foránea: el registro de consumo tiene su propia conservación.
    execution_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
