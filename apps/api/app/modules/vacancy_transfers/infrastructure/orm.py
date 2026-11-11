"""Tablas de transferencias e historial de responsables (esquema ``vacancy``)."""

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


class VacancyTransferRow(Base):
    __tablename__ = "vacancy_transfers"
    __table_args__ = {"schema": SCHEMA_VACANCY}

    # Lo elige quien inicia la operación: repetirla con el mismo valor no la duplica.
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    kind: Mapped[str] = mapped_column(sa.String(20))
    from_user_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    to_user_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    reason: Mapped[str] = mapped_column(sa.Unicode(500))
    requested_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    vacancies_transferred: Mapped[int] = mapped_column(sa.Integer)
    memberships_revoked: Mapped[int] = mapped_column(sa.Integer)
    grants_revoked: Mapped[int] = mapped_column(sa.Integer)
    user_deactivated: Mapped[bool] = mapped_column(sa.Boolean)


class VacancyOwnershipHistoryRow(Base):
    __tablename__ = "vacancy_ownership_history"
    __table_args__ = (
        sa.Index("ix_vacancy_ownership_history_vacancy", "vacancy_id", "changed_at"),
        {"schema": SCHEMA_VACANCY},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_VACANCY}.vacancies.id")
    )
    previous_owner_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
    new_owner_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    reason: Mapped[str] = mapped_column(sa.Unicode(500))
    authorized_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_VACANCY}.vacancy_transfers.id"), nullable=True
    )
