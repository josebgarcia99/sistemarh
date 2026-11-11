"""Tablas de reclutamiento operativo (esquema ``recruitment``)."""

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
    SCHEMA_RECRUITMENT,
    SCHEMA_VACANCY,
    Base,
    UTCDateTime,
)

_S = SCHEMA_RECRUITMENT
_USER_FK = f"{SCHEMA_AUTH}.users.id"
_STAGE_FK = f"{_S}.pipeline_stages.id"


class PipelineVersionRow(Base):
    __tablename__ = "pipeline_versions"
    __table_args__ = (
        sa.UniqueConstraint("version_number", name="uq_pipeline_versions_number"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    version_number: Mapped[int] = mapped_column(sa.Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )


class PipelineStageRow(Base):
    __tablename__ = "pipeline_stages"
    __table_args__ = (
        sa.UniqueConstraint("pipeline_version_id", "position", name="uq_pipeline_stages_position"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    pipeline_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{_S}.pipeline_versions.id")
    )
    position: Mapped[int] = mapped_column(sa.Integer)
    name: Mapped[str] = mapped_column(sa.Unicode(100))
    kind: Mapped[str] = mapped_column(sa.String(30))
    is_optional: Mapped[bool] = mapped_column(sa.Boolean)


class CampaignRow(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        sa.UniqueConstraint("vacancy_id", "number", name="uq_campaigns_number"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_VACANCY}.vacancies.id")
    )
    number: Mapped[int] = mapped_column(sa.Integer)
    name: Mapped[str] = mapped_column(sa.Unicode(100))
    status: Mapped[str] = mapped_column(sa.String(20))
    pipeline_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{_S}.pipeline_versions.id")
    )
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime)
    opened_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )


class CandidateRow(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        # Un correo identifica a una sola persona; sin correo no hay restricción.
        sa.Index(
            "uq_candidates_email",
            "email",
            unique=True,
            mssql_where=sa.text("email IS NOT NULL"),
            sqlite_where=sa.text("email IS NOT NULL"),
        ),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    full_name: Mapped[str] = mapped_column(sa.Unicode(200))
    # Siempre en minúsculas.
    email: Mapped[str | None] = mapped_column(sa.Unicode(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.Unicode(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ApplicationRow(Base):
    __tablename__ = "applications"
    __table_args__ = (
        sa.UniqueConstraint("candidate_id", "campaign_id", name="uq_applications_candidate"),
        sa.Index("ix_applications_campaign", "campaign_id", "stage_id", "status"),
        sa.Index("ix_applications_vacancy", "vacancy_id"),
        sa.Index("ix_applications_file", "cv_file_id"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{_S}.candidates.id"))
    campaign_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{_S}.campaigns.id"))
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_VACANCY}.vacancies.id")
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_STAGE_FK))
    status: Mapped[str] = mapped_column(sa.String(20))
    cv_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_FILES}.file_assets.id"), nullable=True
    )
    evaluation_item_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_AI}.cv_batch_items.id"), nullable=True
    )
    ai_classification: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    ai_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ApplicationMovementRow(Base):
    __tablename__ = "application_movements"
    __table_args__ = (
        sa.UniqueConstraint("application_id", "sequence", name="uq_application_movements_sequence"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{_S}.applications.id"))
    sequence: Mapped[int] = mapped_column(sa.Integer)
    kind: Mapped[str] = mapped_column(sa.String(20))
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_STAGE_FK), nullable=True
    )
    to_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_STAGE_FK), nullable=True
    )
    note: Mapped[str | None] = mapped_column(sa.Unicode(500), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
