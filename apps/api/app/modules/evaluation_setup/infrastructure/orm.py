"""Tablas del perfil de puesto (esquema ``vacancy``) y del prompt (esquema ``ai``)."""

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

_USER_FK = f"{SCHEMA_AUTH}.users.id"
_VACANCY_FK = f"{SCHEMA_VACANCY}.vacancies.id"


class JobProfileVersionRow(Base):
    __tablename__ = "job_profile_versions"
    __table_args__ = (
        sa.UniqueConstraint("vacancy_id", "version_number", name="uq_job_profile_versions_number"),
        {"schema": SCHEMA_VACANCY},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_VACANCY_FK))
    version_number: Mapped[int] = mapped_column(sa.Integer)
    origin: Mapped[str] = mapped_column(sa.String(20))
    content: Mapped[str] = mapped_column(long_text())
    change_note: Mapped[str | None] = mapped_column(sa.Unicode(300), nullable=True)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_FILES}.file_assets.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))


class PromptVersionRow(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        sa.UniqueConstraint("vacancy_id", "version_number", name="uq_prompt_versions_number"),
        sa.Index("ix_prompt_versions_vacancy_status", "vacancy_id", "status"),
        {"schema": SCHEMA_AI},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_VACANCY_FK))
    version_number: Mapped[int] = mapped_column(sa.Integer)
    status: Mapped[str] = mapped_column(sa.String(20))
    profile_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_VACANCY}.job_profile_versions.id")
    )
    pass_threshold: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2))
    layers: Mapped[str] = mapped_column(long_text())
    revision: Mapped[int] = mapped_column(sa.Integer)
    duplicated_from: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_AI}.prompt_versions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    archived_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )


class RubricCriterionRow(Base):
    __tablename__ = "rubric_criteria"
    __table_args__ = (
        sa.UniqueConstraint("prompt_version_id", "position", name="uq_rubric_criteria_position"),
        {"schema": SCHEMA_AI},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    prompt_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_AI}.prompt_versions.id")
    )
    position: Mapped[int] = mapped_column(sa.Integer)
    name: Mapped[str] = mapped_column(sa.Unicode(200))
    description: Mapped[str] = mapped_column(sa.Unicode(1000))
    kind: Mapped[str] = mapped_column(sa.String(20))
    weight: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2))
    levels: Mapped[str] = mapped_column(long_text())
    origin: Mapped[str] = mapped_column(sa.String(20))
