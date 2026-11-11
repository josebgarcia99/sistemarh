"""Tablas de vacantes y acceso (esquema ``vacancy``)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    GUID,
    SCHEMA_AUTH,
    SCHEMA_VACANCY,
    Base,
    UTCDateTime,
)

_USER_FK = f"{SCHEMA_AUTH}.users.id"
_VACANCY_FK = f"{SCHEMA_VACANCY}.vacancies.id"
_ACTIVE = sa.text("revoked_at IS NULL")


class VacancyRow(Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        sa.Index("ix_vacancies_owner", "owner_user_id", "status"),
        sa.Index("ix_vacancies_status", "status"),
        {"schema": SCHEMA_VACANCY},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Unicode(200))
    department: Mapped[str] = mapped_column(sa.Unicode(120))
    location: Mapped[str] = mapped_column(sa.Unicode(120))
    work_mode: Mapped[str] = mapped_column(sa.String(20))
    contract_type: Mapped[str] = mapped_column(sa.Unicode(80))
    description: Mapped[str] = mapped_column(sa.UnicodeText)
    positions: Mapped[int] = mapped_column(sa.Integer)
    notes: Mapped[str | None] = mapped_column(sa.UnicodeText, nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20))
    # Obligatorio: ninguna vacante puede quedar sin responsable.
    owner_user_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    opened_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    version: Mapped[int] = mapped_column(sa.Integer)


class VacancyMemberRow(Base):
    __tablename__ = "vacancy_members"
    __table_args__ = (
        # Un solo acceso vigente por usuario y vacante; los revocados se conservan.
        sa.Index(
            "uq_vacancy_members_active",
            "vacancy_id",
            "user_id",
            unique=True,
            mssql_where=_ACTIVE,
            sqlite_where=_ACTIVE,
        ),
        sa.Index("ix_vacancy_members_user", "user_id"),
        {"schema": SCHEMA_VACANCY},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_VACANCY_FK))
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    access_type: Mapped[str] = mapped_column(sa.String(20))
    granted_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    granted_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )


class VacancySensitiveGrantRow(Base):
    __tablename__ = "vacancy_sensitive_grants"
    __table_args__ = (
        sa.Index(
            "uq_vacancy_sensitive_grants_active",
            "vacancy_id",
            "user_id",
            "document_class",
            unique=True,
            mssql_where=_ACTIVE,
            sqlite_where=_ACTIVE,
        ),
        sa.Index("ix_vacancy_sensitive_grants_user", "user_id"),
        {"schema": SCHEMA_VACANCY},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_VACANCY_FK))
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    document_class: Mapped[str] = mapped_column(sa.String(40))
    granted_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    granted_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
