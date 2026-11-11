"""Tablas de evaluaciones posteriores y síntesis (esquema ``recruitment``)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    GUID,
    SCHEMA_AUTH,
    SCHEMA_FILES,
    SCHEMA_RECRUITMENT,
    SCHEMA_VACANCY,
    Base,
    UTCDateTime,
    long_text,
)

_S = SCHEMA_RECRUITMENT
_USER_FK = f"{SCHEMA_AUTH}.users.id"
_VACANCY_FK = f"{SCHEMA_VACANCY}.vacancies.id"
_APPLICATION_FK = f"{_S}.applications.id"


class FormTemplateRow(Base):
    __tablename__ = "form_templates"
    __table_args__ = {"schema": _S}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Unicode(150))
    description: Mapped[str | None] = mapped_column(sa.Unicode(500), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class FormTemplateVersionRow(Base):
    __tablename__ = "form_template_versions"
    __table_args__ = (
        sa.UniqueConstraint(
            "template_id", "version_number", name="uq_form_template_versions_number"
        ),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    template_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{_S}.form_templates.id"))
    version_number: Mapped[int] = mapped_column(sa.Integer)
    # Secciones y campos, en JSON.
    sections: Mapped[str] = mapped_column(long_text())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )


class AssessmentRow(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        sa.Index("ix_assessments_application", "application_id", "kind"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_APPLICATION_FK))
    vacancy_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_VACANCY_FK))
    kind: Mapped[str] = mapped_column(sa.String(30))
    status: Mapped[str] = mapped_column(sa.String(20))
    event_date: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_FILES}.file_assets.id"), nullable=True
    )
    template_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{_S}.form_template_versions.id"), nullable=True
    )
    data: Mapped[str] = mapped_column(long_text())
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(long_text(), nullable=True)
    ai_summary_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    ai_summary_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    version: Mapped[int] = mapped_column(sa.Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))


class ApplicationSynthesisRow(Base):
    __tablename__ = "application_syntheses"
    __table_args__ = (
        sa.Index("ix_application_syntheses_application", "application_id", "created_at"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_APPLICATION_FK))
    vacancy_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_VACANCY_FK))
    result: Mapped[str] = mapped_column(long_text())
    sources: Mapped[str] = mapped_column(long_text())
    includes_psychometrics: Mapped[bool] = mapped_column(sa.Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
