"""Tablas de bancos de preguntas y llamadas (esquema ``recruitment``)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    GUID,
    SCHEMA_AUTH,
    SCHEMA_RECRUITMENT,
    SCHEMA_VACANCY,
    Base,
    UTCDateTime,
    long_text,
)

_S = SCHEMA_RECRUITMENT
_USER_FK = f"{SCHEMA_AUTH}.users.id"


class QuestionBankRow(Base):
    __tablename__ = "question_banks"
    __table_args__ = (
        sa.Index("ix_question_banks_owner", "owner_user_id", "status"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Unicode(150))
    description: Mapped[str | None] = mapped_column(sa.Unicode(500), nullable=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    scope: Mapped[str] = mapped_column(sa.String(20))
    status: Mapped[str] = mapped_column(sa.String(20))
    duplicated_from: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{_S}.question_banks.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class QuestionBankVersionRow(Base):
    __tablename__ = "question_bank_versions"
    __table_args__ = (
        sa.UniqueConstraint("bank_id", "version_number", name="uq_question_bank_versions_number"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    bank_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{_S}.question_banks.id"))
    version_number: Mapped[int] = mapped_column(sa.Integer)
    # Preguntas en orden, en JSON: id, texto, competencia, guía y origen.
    questions: Mapped[str] = mapped_column(long_text())
    change_note: Mapped[str | None] = mapped_column(sa.Unicode(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))


class CallSessionRow(Base):
    __tablename__ = "call_sessions"
    __table_args__ = (
        sa.Index("ix_call_sessions_application", "application_id", "called_at"),
        {"schema": _S},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{_S}.applications.id"))
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_VACANCY}.vacancies.id")
    )
    bank_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{_S}.question_bank_versions.id")
    )
    status: Mapped[str] = mapped_column(sa.String(20))
    called_at: Mapped[datetime] = mapped_column(UTCDateTime)
    notes: Mapped[str] = mapped_column(long_text())
    # Respuestas en JSON: pregunta, respuesta, observación y si no se realizó.
    answers: Mapped[str] = mapped_column(long_text())
    analysis: Mapped[str | None] = mapped_column(long_text(), nullable=True)
    analysis_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    analysis_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
